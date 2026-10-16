import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import add_audit_log, get_current_user, get_db
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

    client = Client(**body.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)

    # Push to Mikrotik (best-effort, don't fail the creation)
    try:
        await _push_to_mikrotik(client, rt, db)
    except MikrotikError:
        pass

    return await db.get(
        Client,
        client.id,
        options=[selectinload(Client.plan), selectinload(Client.router)],
    )


@router.get("/{client_id}", response_model=ClientResponse)
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


@router.put("/{client_id}", response_model=ClientResponse)
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

    updates = body.model_dump(exclude_unset=True)

    if "ip_address" in updates and updates["ip_address"] != client.ip_address:
        dup = await db.execute(select(Client).where(Client.ip_address == updates["ip_address"]))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"La IP {updates['ip_address']} ya está en uso")

    old_plan_id = client.plan_id
    for field, value in updates.items():
        setattr(client, field, value)

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

    await db.refresh(client)
    resp = ClientResponse.model_validate(client)
    resp.mikrotik_error = mt_error
    resp.mikrotik_sync = mt_sync
    return resp


@router.delete("/{client_id}", status_code=204)
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


@router.post("/{client_id}/suspend", response_model=ClientResponse)
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


@router.post("/{client_id}/activate", response_model=ClientResponse)
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
        print(f"[SYNC-MT] client={client_id} OK: {action}", flush=True)
        return {"ok": True, "message": action or "Queue sincronizada correctamente"}
    except (MikrotikError, Exception) as e:
        detail = str(e) or type(e).__name__
        print(f"[SYNC-MT] client={client_id} ERROR: {detail}", flush=True)
        raise HTTPException(status_code=503, detail=detail)


@router.post("/{client_id}/cancel", response_model=ClientResponse)
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
