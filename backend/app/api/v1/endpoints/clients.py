import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import ACTION_DENIED, add_audit_log, get_current_user, get_db, has_action, require_action
from app.core.security import decrypt_value, encrypt_value
from app.models.client import Client, ClientStatus
from app.models.config import SystemConfig
from app.models.invoice import Invoice
from app.models.plan import Plan
from app.models.router import MikrotikRouter
from app.schemas.client import ClientCreate, ClientListResponse, ClientResponse, ClientUpdate
from app.schemas.invoice import InvoiceResponse
from app.services.mikrotik import MikrotikError, build_service_from_router

router = APIRouter()


async def _get_suspension_config(db: AsyncSession) -> tuple[str, str]:
    """Returns (action, speed): action='disable'|'throttle', speed='64k'"""
    rows = (await db.execute(
        select(SystemConfig).where(SystemConfig.key.in_(["suspension_action", "suspension_speed"]))
    )).scalars().all()
    cfg = {r.key: r.value for r in rows}
    return cfg.get("suspension_action", "disable"), cfg.get("suspension_speed", "64k")


async def _push_to_mikrotik(client: Client, router_obj: MikrotikRouter, db) -> str:
    """Sync a single client's queue to its Mikrotik router. Returns a description of what was done."""
    plan = await db.get(Plan, client.plan_id)
    if not plan:
        return "sin plan"

    is_suspended = client.status == ClientStatus.suspended
    suspension_action, suspension_speed = await _get_suspension_config(db)

    if is_suspended and suspension_action == "throttle":
        effective_max_limit = f"{suspension_speed}/{suspension_speed}"
        effective_disabled = False
    else:
        effective_max_limit = plan.mikrotik_max_limit
        effective_disabled = is_suspended

    def _sync() -> str:
        svc = build_service_from_router(router_obj)
        with svc:
            use_sfq = svc.has_queue_type("guaynet-sfq")
            existing = svc.get_queue_by_name(client.mikrotik_queue_name)
            update_params = {
                "max_limit": effective_max_limit,
                "disabled": effective_disabled,
                "comment": f"guaynet:{client.id}|{client.full_name}",
            }
            if not is_suspended and plan.mikrotik_burst_limit and plan.mikrotik_burst_threshold:
                update_params["burst_limit"] = plan.mikrotik_burst_limit
                update_params["burst_threshold"] = plan.mikrotik_burst_threshold
                update_params["burst_time"] = plan.mikrotik_burst_time
            if use_sfq:
                update_params["queue_type"] = "guaynet-sfq"
            if existing:
                svc.update_simple_queue(existing["id"], **update_params)
                return f"updated {client.mikrotik_queue_name} → {effective_max_limit}"
            else:
                svc.add_simple_queue(
                    name=client.mikrotik_queue_name,
                    target=client.mikrotik_target,
                    **update_params,
                )
                return f"created {client.mikrotik_queue_name} → {effective_max_limit}"

    return await asyncio.to_thread(_sync)


async def _sync_pppoe_to_mikrotik(client: Client, db: AsyncSession) -> str:
    if not client.pppoe_username or not client.pppoe_password_encrypted:
        return "no_pppoe"
    if not client.router_id:
        return "no_router"
    rt = await db.get(MikrotikRouter, client.router_id)
    if not rt or not rt.password_encrypted:
        return "no_router"
    pppoe_password = decrypt_value(client.pppoe_password_encrypted)
    disabled = client.status != ClientStatus.active

    def _sync():
        svc = build_service_from_router(rt)
        with svc:
            existing = svc.get_pppoe_secrets()
            found = next((s for s in existing if s.get("name") == client.pppoe_username), None)
            if found:
                return svc.update_pppoe_secret(
                    client.pppoe_username,
                    password=pppoe_password,
                    ip_address=client.ip_address,
                    disabled=disabled,
                )
            else:
                return svc.add_pppoe_secret(
                    client.pppoe_username,
                    pppoe_password,
                    client.ip_address,
                    comment=f"guaynet-client-{client.id}",
                )

    success = await asyncio.to_thread(_sync)
    return "synced" if success else "error"


@router.get("/", response_model=List[ClientListResponse])
async def list_clients(
    status: Optional[ClientStatus] = None,
    router_id: Optional[int] = None,
    plan_id: Optional[int] = None,
    search: Optional[str] = Query(None, description="Busca por nombre, IP o teléfono"),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = (
        select(Client)
        .options(selectinload(Client.plan), selectinload(Client.router))
        .order_by(Client.last_name, Client.first_name)
    )
    if status:
        q = q.where(Client.status == status)
    if router_id:
        q = q.where(Client.router_id == router_id)
    if plan_id:
        q = q.where(Client.plan_id == plan_id)
    if search:
        term = f"%{search}%"
        q = q.where(
            or_(
                func.lower(Client.first_name + " " + Client.last_name).like(func.lower(term)),
                Client.ip_address.like(term),
                Client.phone.like(term),
                Client.dni.like(term),
            )
        )
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/connection-status")
async def get_clients_connection_status(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Read-only live status from MikroTik ARP tables; failures remain unknown, not offline."""
    clients_result = await db.execute(
        select(Client).where(Client.status != ClientStatus.cancelled)
    )
    clients = clients_result.scalars().all()
    routers = {}
    for client in clients:
        if client.router_id and client.router_id not in routers:
            routers[client.router_id] = await db.get(MikrotikRouter, client.router_id)

    result = {}
    checked_at = datetime.now(timezone.utc).isoformat()
    for router_id, router_obj in routers.items():
        if not router_obj:
            continue
        router_clients = [c for c in clients if c.router_id == router_id]
        try:
            def _read_arp():
                svc = build_service_from_router(router_obj)
                with svc:
                    return svc.get_arp_table()

            arp_rows = await asyncio.to_thread(_read_arp)
            live_ips = set()
            live_macs = set()
            for row in arp_rows:
                if row.get("address") and row.get("complete", "true") != "false":
                    live_ips.add(row["address"])
                    mac = (row.get("mac-address") or "").replace("-", ":").upper()
                    if mac:
                        live_macs.add(mac)
            for client in router_clients:
                mac = (client.mac_address or "").replace("-", ":").upper()
                result[str(client.id)] = {
                    "status": "online" if client.ip_address in live_ips or (mac and mac in live_macs) else "not_detected",
                    "checked_at": checked_at,
                }
        except Exception as e:
            logger.warning("Could not read ARP status for router %s: %s", router_id, e)
            for client in router_clients:
                result[str(client.id)] = {"status": "unknown", "checked_at": checked_at}

    return result


@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(
    body: ClientCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    # Check IP uniqueness
    existing_ip = await db.execute(select(Client).where(Client.ip_address == body.ip_address))
    if existing_ip.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"La IP {body.ip_address} ya está en uso")

    # Validate plan and router exist
    plan = await db.get(Plan, body.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    rt = await db.get(MikrotikRouter, body.router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    data = body.model_dump()
    pppoe_pw = data.pop("pppoe_password", None)
    client = Client(**data)
    if pppoe_pw:
        client.pppoe_password_encrypted = encrypt_value(pppoe_pw)
    db.add(client)
    await db.commit()
    await db.refresh(client)

    # Push to Mikrotik (best-effort, don't fail the creation)
    try:
        await _push_to_mikrotik(client, rt, db)
    except MikrotikError:
        pass
    try:
        await _sync_pppoe_to_mikrotik(client, db)
    except Exception:
        pass

    return await db.get(
        Client,
        client.id,
        options=[selectinload(Client.plan), selectinload(Client.router)],
    )


# ":int" so fixed paths declared further down (/resolve-location) are not taken as an id
@router.get("/{client_id:int}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.plan), selectinload(Client.router))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.put("/{client_id:int}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    body: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.plan), selectinload(Client.router))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if body.status is not None and body.status != client.status \
            and not await has_action(db, current_user, "act_client_service"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)

    updates = body.model_dump(exclude_unset=True)
    pppoe_pw = updates.pop("pppoe_password", None)

    if "ip_address" in updates and updates["ip_address"] != client.ip_address:
        dup = await db.execute(select(Client).where(Client.ip_address == updates["ip_address"]))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"La IP {updates['ip_address']} ya está en uso")

    old_plan_id = client.plan_id
    for field, value in updates.items():
        setattr(client, field, value)
    if pppoe_pw:
        client.pppoe_password_encrypted = encrypt_value(pppoe_pw)

    if "plan_id" in updates and updates["plan_id"] != old_plan_id:
        add_audit_log(db, current_user, "plan_change", "client", client.id, client.full_name,
                      details=f"plan {old_plan_id} → {updates['plan_id']}")

    db.add(client)
    await db.commit()

    mt_error = None
    mt_sync = None
    rt = await db.get(MikrotikRouter, client.router_id)
    if rt:
        try:
            mt_sync = await _push_to_mikrotik(client, rt, db)
        except MikrotikError as e:
            mt_error = str(e)
        except Exception as e:
            mt_error = f"Error inesperado: {e}"
    else:
        mt_error = "Router no encontrado"

    try:
        await _sync_pppoe_to_mikrotik(client, db)
    except Exception:
        pass

    await db.refresh(client)
    resp = ClientResponse.model_validate(client)
    resp.has_pppoe = bool(client.pppoe_password_encrypted)
    resp.mikrotik_error = mt_error
    resp.mikrotik_sync = mt_sync
    return resp


@router.delete("/{client_id:int}", status_code=204, dependencies=[Depends(require_action("act_client_delete"))])
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    rt = await db.get(MikrotikRouter, client.router_id)
    if rt:
        def _remove():
            from app.services.mikrotik import build_service_from_router
            svc = build_service_from_router(rt)
            with svc:
                q = svc.get_queue_by_name(client.mikrotik_queue_name)
                if q:
                    svc.remove_queue(q["id"])
        try:
            await asyncio.to_thread(_remove)
        except MikrotikError:
            pass

    await db.delete(client)
    await db.commit()


@router.post("/{client_id}/suspend", response_model=ClientResponse, dependencies=[Depends(require_action("act_client_service"))])
async def suspend_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Client).options(selectinload(Client.plan), selectinload(Client.router)).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    client.status = ClientStatus.suspended
    add_audit_log(db, current_user, "suspend", "client", client.id, client.full_name)
    db.add(client)
    await db.commit()

    mt_error = None
    rt = await db.get(MikrotikRouter, client.router_id)
    if rt:
        try:
            await _push_to_mikrotik(client, rt, db)
        except (MikrotikError, Exception) as e:
            mt_error = str(e)

    from app.services.telegram import send_telegram
    await send_telegram(f"⛔ *Servicio suspendido*\n{client.full_name} ({client.ip_address})")

    await db.refresh(client)
    resp = ClientResponse.model_validate(client)
    resp.mikrotik_error = mt_error
    return resp


@router.post("/{client_id}/activate", response_model=ClientResponse, dependencies=[Depends(require_action("act_client_service"))])
async def activate_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Client).options(selectinload(Client.plan), selectinload(Client.router)).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    client.status = ClientStatus.active
    add_audit_log(db, current_user, "activate", "client", client.id, client.full_name)
    db.add(client)
    await db.commit()

    mt_error = None
    rt = await db.get(MikrotikRouter, client.router_id)
    if rt:
        try:
            await _push_to_mikrotik(client, rt, db)
        except (MikrotikError, Exception) as e:
            mt_error = str(e)

    from app.services.telegram import send_telegram
    await send_telegram(f"✅ *Servicio activado*\n{client.full_name} ({client.ip_address})")

    await db.refresh(client)
    resp = ClientResponse.model_validate(client)
    resp.mikrotik_error = mt_error
    return resp


@router.post("/{client_id}/sync-mikrotik", status_code=200)
async def sync_client_mikrotik(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Force-push this client's queue config to its router."""
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    rt = await db.get(MikrotikRouter, client.router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    try:
        action = await _push_to_mikrotik(client, rt, db)
        return {"ok": True, "message": action or "Queue sincronizada correctamente"}
    except (MikrotikError, Exception) as e:
        detail = str(e) or type(e).__name__
        raise HTTPException(status_code=503, detail=detail)


@router.post("/{client_id}/sync-pppoe")
async def sync_client_pppoe(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    status = await _sync_pppoe_to_mikrotik(client, db)
    return {"status": status}


@router.post("/{client_id}/cancel", response_model=ClientResponse, dependencies=[Depends(require_action("act_client_service"))])
async def cancel_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Mark client as cancelled, remove Mikrotik queue, free Ubiquiti device."""
    result = await db.execute(
        select(Client).options(selectinload(Client.plan), selectinload(Client.router)).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if client.status == ClientStatus.cancelled:
        raise HTTPException(status_code=400, detail="El cliente ya fue dado de baja")

    rt = await db.get(MikrotikRouter, client.router_id)
    if rt:
        def _remove():
            svc = build_service_from_router(rt)
            with svc:
                q = svc.get_queue_by_name(client.mikrotik_queue_name)
                if q:
                    svc.remove_queue(q["id"])
        try:
            await asyncio.to_thread(_remove)
        except MikrotikError:
            pass

    client.ubiquiti_device_id = None
    client.status = ClientStatus.cancelled
    add_audit_log(db, current_user, "cancel", "client", client.id, client.full_name)
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


@router.get("/resolve-location")
async def resolve_location_url(
    url: str,
    _=Depends(get_current_user),
):
    """Follow redirects on a shortened Maps URL and return the final URL so the frontend can parse coordinates."""
    import httpx
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=6.0) as client:
            r = await client.head(url)
            return {"resolved_url": str(r.url)}
    except Exception as e:
        raise HTTPException(400, f"No se pudo resolver la URL: {e}")


@router.get("/{client_id}/invoices", response_model=List[InvoiceResponse])
async def get_client_invoices(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    result = await db.execute(
        select(Invoice)
        .where(Invoice.client_id == client_id)
        .order_by(Invoice.due_date.desc())
    )
    return result.scalars().all()
