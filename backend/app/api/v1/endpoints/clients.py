import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import ACTION_DENIED, add_audit_log, get_current_user, get_db, has_action, require_action
from app.core.security import decrypt_value, encrypt_value
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice
from app.models.plan import Plan
from app.models.router import MikrotikRouter
from app.schemas.client import ClientCreate, ClientListResponse, ClientResponse, ClientUpdate
from app.schemas.invoice import InvoiceResponse
from app.services.mikrotik import build_service_from_router
from app.services.provisioning import provision_client, remove_from_router

router = APIRouter()


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
    response: Response,
    status: Optional[ClientStatus] = None,
    router_id: Optional[int] = None,
    plan_id: Optional[int] = None,
    search: Optional[str] = Query(None, description="Busca por nombre, IP, teléfono, DNI, MAC o email"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """One page of clients. The total that match goes in the X-Total-Count header
    (the panel paginates with it; before, lists stopped at 100 without saying so)."""
    filters = []
    if status:
        filters.append(Client.status == status)
    if router_id:
        filters.append(Client.router_id == router_id)
    if plan_id:
        filters.append(Client.plan_id == plan_id)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        filters.append(or_(
            func.lower(Client.first_name + " " + Client.last_name).like(term),
            Client.ip_address.like(term),
            Client.phone.like(term),
            Client.dni.like(term),
            func.lower(Client.mac_address).like(term),
            func.lower(Client.email).like(term),
        ))
    total = (await db.execute(select(func.count()).select_from(Client).where(*filters))).scalar() or 0
    response.headers["X-Total-Count"] = str(total)
    q = (
        select(Client)
        .options(selectinload(Client.plan), selectinload(Client.router))
        .where(*filters)
        .order_by(Client.last_name, Client.first_name, Client.id)
        .offset(skip).limit(limit)
    )
    return (await db.execute(q)).scalars().all()


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
    current_user=Depends(get_current_user),
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
    await db.flush()
    add_audit_log(db, current_user, "create", "client", client.id, client.full_name,
                  f"Plan {plan.name} · IP {client.ip_address}")
    await db.commit()
    await db.refresh(client)

    # Applied to the MikroTik right away, with a time limit: an unreachable router
    # does not block the save, the response says so.
    result = await provision_client(db, client)
    pppoe = await _sync_pppoe_to_mikrotik(client, db) if client.pppoe_username else None
    client = await db.get(Client, client.id, options=[selectinload(Client.plan), selectinload(Client.router)])
    resp = ClientResponse.model_validate(client)
    resp.has_pppoe = bool(client.pppoe_password_encrypted)
    resp.mikrotik_sync = result.message if result.ok else None
    resp.mikrotik_error = None if result.ok else result.message
    if pppoe == "error":
        resp.mikrotik_error = ((resp.mikrotik_error + "; ") if resp.mikrotik_error else "") + "No se pudo crear el usuario PPPoE"
    return resp


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


# ── Client record (ficha 360) ─────────────────────────────────────────────────

async def _client_or_404(db: AsyncSession, client_id: int) -> Client:
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.get("/{client_id:int}/summary")
async def client_summary(client_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """Balance and counters for the header of the client record. Money only for users who see billing."""
    from app.core.deps import _is_admin, effective_permissions
    from app.models.invoice import InvoiceStatus, Payment
    from app.models.ticket import Ticket, TicketStatus
    from app.models.work_order import WorkOrder

    await _client_or_404(db, client_id)
    sees_billing = _is_admin(current_user) or (await effective_permissions(db, current_user)).get("billing", (False, False))[0]
    from app.services.account import client_balance, unpaid_invoices

    bal = await client_balance(db, client_id)
    unpaid = await unpaid_invoices(db, client_id)
    overdue = [i for i in unpaid if i.status == InvoiceStatus.overdue]
    last_payment = (await db.execute(
        select(Payment).where(Payment.client_id == client_id, Payment.voided_at.is_(None))
        .order_by(Payment.payment_date.desc(), Payment.id.desc()).limit(1)
    )).scalar_one_or_none()
    last_total = 0.0
    if last_payment:  # the whole cobro, even if it was split across invoices
        last_total = float((await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.group_id == last_payment.group_id, Payment.voided_at.is_(None))
        )).scalar() or 0) if last_payment.group_id else float(last_payment.amount)
    open_tickets = (await db.execute(select(func.count()).select_from(Ticket).where(
        Ticket.client_id == client_id, Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress])
    ))).scalar() or 0
    open_orders = (await db.execute(select(func.count()).select_from(WorkOrder).where(
        WorkOrder.client_id == client_id, WorkOrder.status.in_(["pending", "in_progress"])
    ))).scalar() or 0
    if not sees_billing:
        return {"balance": None, "credit": None, "unpaid_count": None, "overdue_count": None, "oldest_overdue_due": None,
                "oldest_unpaid_invoice_id": None, "last_payment": None,
                "open_tickets": open_tickets, "open_work_orders": open_orders}
    return {
        "balance": bal.balance,
        "credit": bal.credit,
        "unpaid_count": len(unpaid),
        "overdue_count": len(overdue),
        "oldest_overdue_due": overdue[0].due_date.isoformat() if overdue else None,
        "oldest_unpaid_invoice_id": unpaid[0].id if unpaid else None,
        "last_payment": {
            "date": last_payment.payment_date.isoformat(),
            "amount": last_total,
            "received_by": last_payment.received_by_name,
            "method": last_payment.method.value if hasattr(last_payment.method, "value") else last_payment.method,
        } if last_payment else None,
        "open_tickets": open_tickets,
        "open_work_orders": open_orders,
    }


@router.get("/{client_id:int}/connection")
async def client_connection(client_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """Whether this client is seen now in its router's ARP table (one router, time-limited)."""
    client = await _client_or_404(db, client_id)
    checked_at = datetime.now(timezone.utc).isoformat()
    router_obj = await db.get(MikrotikRouter, client.router_id) if client.router_id else None
    if not router_obj:
        return {"status": "unknown", "checked_at": checked_at, "detail": "Sin router asignado"}

    def _read():
        with build_service_from_router(router_obj) as svc:
            return svc.get_arp_table()

    try:
        rows = await asyncio.wait_for(asyncio.to_thread(_read), 10)
    except Exception as exc:
        logger.info("ARP read for client %s failed: %s", client_id, exc)
        return {"status": "unknown", "checked_at": checked_at, "detail": f"El router {router_obj.name} no respondió"}
    mac = (client.mac_address or "").replace("-", ":").upper()
    for row in rows:
        row_mac = (row.get("mac-address") or "").replace("-", ":").upper()
        # librouteros turns "true"/"false" into booleans; an incomplete/invalid entry is not a live device
        if str(row.get("complete", True)).lower() == "false" or str(row.get("invalid", False)).lower() == "true":
            continue
        if row.get("address") == client.ip_address or (mac and row_mac == mac):
            return {"status": "online", "checked_at": checked_at, "mac_seen": row_mac or None,
                    "ip_seen": row.get("address"), "interface": row.get("interface")}
    return {"status": "not_detected", "checked_at": checked_at}


@router.get("/{client_id:int}/history")
async def client_history(client_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """What was done on this client (audit log), newest first."""
    from app.models.audit import AuditLog

    await _client_or_404(db, client_id)
    rows = (await db.execute(
        select(AuditLog).where(AuditLog.entity_type == "client", AuditLog.entity_id == client_id)
        .order_by(AuditLog.created_at.desc()).limit(200)
    )).scalars().all()
    return [{"id": r.id, "action": r.action, "username": r.username, "details": r.details,
             "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]


class NoteCreate(BaseModel):
    body: str


@router.get("/{client_id:int}/notes")
async def list_client_notes(client_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    from app.models.client_note import ClientNote

    await _client_or_404(db, client_id)
    rows = (await db.execute(
        select(ClientNote).where(ClientNote.client_id == client_id).order_by(ClientNote.created_at.desc()).limit(200)
    )).scalars().all()
    return [{"id": n.id, "body": n.body, "username": n.username,
             "created_at": n.created_at.isoformat() if n.created_at else None} for n in rows]


@router.post("/{client_id:int}/notes", status_code=201)
async def add_client_note(
    client_id: int, body: NoteCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user),
):
    from app.models.client_note import ClientNote

    await _client_or_404(db, client_id)
    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=422, detail="La nota está vacía")
    if len(text) > 4000:
        raise HTTPException(status_code=422, detail="La nota es demasiado larga (máximo 4000 caracteres)")
    note = ClientNote(client_id=client_id, user_id=current_user.id,
                      username=current_user.full_name or current_user.username, body=text)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return {"id": note.id, "body": note.body, "username": note.username,
            "created_at": note.created_at.isoformat() if note.created_at else None}


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
    old_router_id = client.router_id
    network_fields = {"plan_id", "ip_address", "status", "router_id"}
    network_changed = any(f in updates and updates[f] != getattr(client, f) for f in network_fields)
    for field, value in updates.items():
        setattr(client, field, value)
    if pppoe_pw:
        client.pppoe_password_encrypted = encrypt_value(pppoe_pw)

    if "plan_id" in updates and updates["plan_id"] != old_plan_id:
        add_audit_log(db, current_user, "plan_change", "client", client.id, client.full_name,
                      details=f"plan {old_plan_id} → {updates['plan_id']}")

    db.add(client)
    await db.commit()
    await db.refresh(client)

    mt_sync, mt_error = None, None
    if network_changed or pppoe_pw:
        if old_router_id and old_router_id != client.router_id:
            moved = await remove_from_router(db, client, old_router_id)
            if not moved.ok:
                mt_error = moved.message
        result = await provision_client(db, client)
        mt_sync = result.message if result.ok else None
        if not result.ok:
            mt_error = ((mt_error + "; ") if mt_error else "") + result.message
        if client.pppoe_username and await _sync_pppoe_to_mikrotik(client, db) == "error":
            mt_error = ((mt_error + "; ") if mt_error else "") + "No se pudo actualizar el usuario PPPoE"

    client = await db.get(Client, client.id, options=[selectinload(Client.plan), selectinload(Client.router)])
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

    await remove_from_router(db, client)

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

    result = await provision_client(db, client)
    mt_error = None if result.ok else result.message

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

    result = await provision_client(db, client)
    mt_error = None if result.ok else result.message

    from app.services.telegram import send_telegram
    await send_telegram(f"✅ *Servicio activado*\n{client.full_name} ({client.ip_address})")

    await db.refresh(client)
    resp = ClientResponse.model_validate(client)
    resp.mikrotik_error = mt_error
    return resp


@router.post("/{client_id}/sync-mikrotik", status_code=200, dependencies=[Depends(require_action("act_client_service"))])
async def sync_client_mikrotik(
    client_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Re-send this client's queue and suspension state to its router."""
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    result = await provision_client(db, client, timeout=60)
    if not result.ok:
        raise HTTPException(status_code=503, detail=result.message)
    return {"ok": True, "message": result.message}


@router.post("/{client_id}/sync-pppoe", dependencies=[Depends(require_action("act_client_service"))])
async def sync_client_pppoe(
    client_id: int,
    db: AsyncSession = Depends(get_db),
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

    await remove_from_router(db, client)

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
    """Follow redirects on a shortened Maps URL and return the final URL so the frontend can parse coordinates.

    Only Google Maps hosts over HTTPS, checked on every hop: an open fetch here
    would let any user make the server probe the internal network (SSRF).
    """
    import httpx

    current = url.strip()
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=6.0) as client:
            for _ in range(_MAPS_MAX_HOPS + 1):
                if not _is_maps_url(current):
                    raise HTTPException(400, "Solo se aceptan enlaces de Google Maps")
                r = await client.head(current)
                location = r.headers.get("location")
                if not r.is_redirect or not location:
                    return {"resolved_url": current}
                current = str(httpx.URL(current).join(location))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "No se pudo resolver el enlace")
    raise HTTPException(400, "El enlace redirige demasiadas veces")


_MAPS_MAX_HOPS = 5
_MAPS_DOMAINS = ("goo.gl", "google.com", "google.com.ar", "g.page")


def _is_maps_url(value: str) -> bool:
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    return (
        parts.scheme == "https"
        and parts.port in (None, 443)
        and any(host == d or host.endswith("." + d) for d in _MAPS_DOMAINS)
    )


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
