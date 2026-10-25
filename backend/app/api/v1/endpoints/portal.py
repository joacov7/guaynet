"""
Client self-service portal.

Two ways to identify the client, both under /api/v1/portal:
- Login (email + password → bearer token): /login, /me, /invoices, /tickets.
- No login, for the security module: by source IP (internet clients),
  by portal link token, or by mobile app device credential:
  /by-ip, /speedtest/*, /security/*.
"""
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.deps import get_db
from app.core.security import create_access_token, get_password_hash, verify_password, decode_token
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.plan import Plan
from app.models.ticket import Ticket, TicketCategory, TicketComment, TicketPriority, TicketStatus
from app.services.security.contracts import AcceptRequest as ContractAcceptRequest

router = APIRouter()

portal_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/portal/login", auto_error=False)

PREFIX = "portal:"


async def get_current_portal_client(
    token: str = Depends(portal_oauth2),
    db: AsyncSession = Depends(get_db),
) -> Client:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise exc
    sub = decode_token(token)
    if not sub or not sub.startswith(PREFIX):
        raise exc
    client_id = int(sub[len(PREFIX):])
    client = await db.get(Client, client_id)
    if not client or not client.portal_enabled:
        raise exc
    return client


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class PortalLoginRequest(BaseModel):
    email: str
    password: str


class PortalClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    status: ClientStatus
    plan_name: Optional[str] = None
    ip_address: str


@router.post("/login")
async def portal_login(body: PortalLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client).options(selectinload(Client.plan)).where(Client.email == body.email)
    )
    client = result.scalar_one_or_none()
    if (
        not client
        or not client.portal_enabled
        or not client.portal_password_hash
        or not verify_password(body.password, client.portal_password_hash)
    ):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    token = create_access_token(f"{PREFIX}{client.id}")
    return {
        "access_token": token,
        "token_type": "bearer",
        "client": PortalClientResponse(
            id=client.id,
            full_name=client.full_name,
            email=client.email,
            phone=client.phone,
            address=client.address,
            status=client.status,
            plan_name=client.plan.name if client.plan else None,
            ip_address=client.ip_address,
        ),
    }


@router.get("/me", response_model=PortalClientResponse)
async def portal_me(
    client: Client = Depends(get_current_portal_client),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Client).options(selectinload(Client.plan)).where(Client.id == client.id)
    )
    c = result.scalar_one()
    return PortalClientResponse(
        id=c.id,
        full_name=c.full_name,
        email=c.email,
        phone=c.phone,
        address=c.address,
        status=c.status,
        plan_name=c.plan.name if c.plan else None,
        ip_address=c.ip_address,
    )


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

class PortalInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    period: Optional[str]
    amount: float
    status: InvoiceStatus
    issue_date: Optional[datetime]
    due_date: Optional[datetime]
    paid_date: Optional[datetime]


@router.get("/invoices", response_model=List[PortalInvoiceResponse])
async def portal_invoices(
    client: Client = Depends(get_current_portal_client),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Invoice)
        .where(Invoice.client_id == client.id)
        .order_by(Invoice.due_date.desc())
        .limit(24)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

class PortalTicketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: TicketCategory = TicketCategory.other


class PortalTicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str]
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    created_at: datetime
    comment_count: int = 0


@router.get("/tickets", response_model=List[PortalTicketResponse])
async def portal_tickets(
    client: Client = Depends(get_current_portal_client),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.comments))
        .where(Ticket.client_id == client.id)
        .order_by(Ticket.created_at.desc())
    )
    tickets = result.scalars().all()
    return [
        PortalTicketResponse(
            id=t.id,
            title=t.title,
            description=t.description,
            status=t.status,
            priority=t.priority,
            category=t.category,
            created_at=t.created_at,
            comment_count=len(t.comments),
        )
        for t in tickets
    ]


@router.post("/tickets", status_code=201)
async def portal_create_ticket(
    body: PortalTicketCreate,
    client: Client = Depends(get_current_portal_client),
    db: AsyncSession = Depends(get_db),
):
    ticket = Ticket(
        client_id=client.id,
        title=body.title,
        description=body.description,
        category=body.category,
        priority=TicketPriority.medium,
        status=TicketStatus.open,
    )
    db.add(ticket)
    await db.commit()
    return {"id": ticket.id}


# ---------------------------------------------------------------------------
# Admin: set portal password for a client
# ---------------------------------------------------------------------------

class SetPortalPassword(BaseModel):
    password: str
    enabled: bool = True


@router.get("/invoices/{invoice_id}/pdf")
async def portal_invoice_pdf(
    invoice_id: int,
    client: Client = Depends(get_current_portal_client),
    db: AsyncSession = Depends(get_db),
):
    invoice = await db.get(Invoice, invoice_id)
    if not invoice or invoice.client_id != client.id:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    from app.api.v1.endpoints.invoices import _build_invoice_pdf
    pdf_bytes = await _build_invoice_pdf(invoice_id, db)
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=factura_{invoice_id}.pdf"},
    )


@router.put("/clients/{client_id}/portal-password")
async def set_portal_password(
    client_id: int,
    body: SetPortalPassword,
    db: AsyncSession = Depends(get_db),
):
    from app.core.deps import require_admin
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    client.portal_password_hash = get_password_hash(body.password)
    client.portal_enabled = body.enabled
    await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Portal without login: identified by IP, portal link token or app device
# ═══════════════════════════════════════════════════════════════════════════

_SPEEDTEST_BLOB = os.urandom(5 * 1024 * 1024)  # 5 MB random payload, generated once at startup


def _client_ip(request: Request) -> str:
    # X-Real-IP is overwritten by our nginx with $remote_addr; X-Forwarded-For is
    # passed through from the client untouched and must never be trusted here.
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else ""


async def _get_client_by_ip(ip: str, db: AsyncSession) -> Optional[Client]:
    result = await db.execute(select(Client).where(Client.ip_address == ip))
    return result.scalar_one_or_none()


# ── Identify ──────────────────────────────────────────────────────────────────

@router.get("/by-ip")
async def portal_by_ip(request: Request, db: AsyncSession = Depends(get_db)):
    """Return the client record that matches the caller's IP, plus plan and recent invoices."""
    ip = _client_ip(request)
    client = await _get_client_by_ip(ip, db)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró ningún cliente registrado para la IP {ip}. "
                   "Si creés que es un error, contactá a tu proveedor.",
        )

    plan = await db.get(Plan, client.plan_id)

    invoices_result = await db.execute(
        select(Invoice)
        .where(Invoice.client_id == client.id)
        .order_by(Invoice.due_date.desc())
        .limit(6)
    )
    invoices = invoices_result.scalars().all()

    return {
        "client": {
            "id": client.id,
            "full_name": client.full_name,
            "ip_address": client.ip_address,
            "status": client.status,
        },
        "plan": {
            "name": plan.name if plan else "—",
            "download_mbps": plan.download_mbps if plan else 0,
            "upload_mbps": plan.upload_mbps if plan else 0,
            "burst_download_mbps": plan.burst_download_mbps if plan else None,
            "burst_upload_mbps": plan.burst_upload_mbps if plan else None,
        } if plan else None,
        "invoices": [
            {
                "id": inv.id,
                "amount": float(inv.amount),
                "status": inv.status,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "period": inv.period if hasattr(inv, "period") else None,
            }
            for inv in invoices
        ],
    }


# ── Speed test ────────────────────────────────────────────────────────────────

@router.get("/speedtest/download")
async def speedtest_download():
    """Returns a fixed 5 MB payload for download speed measurement."""
    return Response(
        content=_SPEEDTEST_BLOB,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "Content-Length": str(len(_SPEEDTEST_BLOB)),
        },
    )


@router.post("/speedtest/upload")
async def speedtest_upload(request: Request):
    """Receives upload payload and returns the number of bytes received."""
    body = await request.body()
    return {"received_bytes": len(body)}


# ── Security portal by token ─────────────────────────────────────────────────

async def _security_payload(sub, prop, db: AsyncSession) -> dict:
    """Security summary shown in the portal and the mobile app."""
    from sqlalchemy import func
    from app.models.security.alert import SecurityAlert
    from app.models.security.event import SecurityEvent
    from app.models.security.report import SecurityMonthlyReport
    from app.models.security.subscription import SecurityPlan

    from app.services.runtime_config import int_param

    plan = await db.get(SecurityPlan, sub.plan_id)

    events_result = await db.execute(
        select(SecurityEvent)
        .where(SecurityEvent.subscription_id == sub.id)
        .order_by(SecurityEvent.occurred_at.desc())
        .limit(5)
    )
    events = events_result.scalars().all()

    alerts_result = await db.execute(
        select(func.count()).select_from(SecurityAlert).where(
            SecurityAlert.subscription_id == sub.id,
            SecurityAlert.status.in_(["new", "acknowledged"]),
        )
    )
    active_alerts = alerts_result.scalar() or 0

    report_result = await db.execute(
        select(SecurityMonthlyReport)
        .where(
            SecurityMonthlyReport.subscription_id == sub.id,
            SecurityMonthlyReport.status == "ready",
        )
        .order_by(SecurityMonthlyReport.period.desc())
        .limit(1)
    )
    last_report = report_result.scalar_one_or_none()

    return {
        "has_subscription": True,
        "subscription": {
            "id": sub.id,
            "status": sub.status.value if hasattr(sub.status, "value") else sub.status,
            "plan_name": plan.name if plan else "—",
            "beat_account_id": sub.beat_account_id,
            "property_name": prop.name if prop else "—",
            "property_address": prop.address if prop else "—",
            "entry_secure_enabled": sub.has_feature("entry_secure"),
            "entry_default_minutes": await int_param("sec_entry_default_minutes"),
        },
        "active_alerts": active_alerts,
        "recent_events": [
            {
                "event_type": e.event_type.value if hasattr(e.event_type, "value") else e.event_type,
                "occurred_at": e.occurred_at.isoformat(),
                "zone_number": e.zone_number,
                "description": e.description,
            }
            for e in events
        ],
        "last_report": {
            "period": last_report.period,
            "event_count": last_report.event_count,
            "alert_count": last_report.alert_count,
        } if last_report else None,
    }


@router.get("/security/token/{token}")
async def portal_security_by_token(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Return the client's security data identified by their portal token.
    Used by clients who don't have internet service with Guaynet.
    """
    from app.models.security.property import Property

    sub = await _resolve_portal_subscription(token, request, db, allow_device=False)
    prop = await db.get(Property, sub.property_id)
    return await _security_payload(sub, prop, db)


# ── Security helpers ──────────────────────────────────────────────────────────

async def _get_security_subscription(client: Client, db: AsyncSession):
    """
    Resolve the active security subscription for an internet client.
    Chain: Client.id → Property.internet_client_id → SecuritySubscription.property_id
    Returns None if no property or no active subscription is found.
    """
    from app.models.security.property import Property
    from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus

    prop_result = await db.execute(
        select(Property).where(Property.internet_client_id == client.id)
    )
    prop = prop_result.scalar_one_or_none()
    if prop is None:
        return None, None

    sub_result = await db.execute(
        select(SecuritySubscription)
        .options(
            selectinload(SecuritySubscription.plan),
            selectinload(SecuritySubscription.features),
        )
        .where(
            SecuritySubscription.property_id == prop.id,
            SecuritySubscription.status == SecuritySubscriptionStatus.active,
        )
    )
    sub = sub_result.scalar_one_or_none()
    return prop, sub


# ── Security portal ───────────────────────────────────────────────────────────

@router.get("/security")
async def portal_security(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Return the client's security subscription status, recent events, and active alerts.
    """
    ip = _client_ip(request)
    client = await _get_client_by_ip(ip, db)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado para esta IP")

    prop, sub = await _get_security_subscription(client, db)
    if sub is None:
        return {"has_subscription": False}
    return await _security_payload(sub, prop, db)


class EntrySessionRequest(BaseModel):
    duration_minutes: Optional[int] = None  # None = default from Seguridad → Configuración
    token: Optional[str] = None  # portal token for non-IP clients


@router.post("/security/entry-session")
async def portal_start_entry_session(
    body: EntrySessionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Client starts an entry secure countdown from the portal.
    No PIN required to start — PIN is used at the panel to cancel (safe arrival).
    If the session expires without being cancelled, an alert is triggered.
    """
    from app.models.security.entry_session import EntrySession, EntrySessionStatus
    from app.schemas.security.entry_session import EntrySessionCreate
    from app.services.security.entry_sessions import start_entry_session

    sub = await _resolve_portal_subscription(body.token, request, db)

    if not sub.has_feature("entry_secure"):
        raise HTTPException(status_code=403, detail="Entrada segura no está habilitada en tu plan")

    # Prevent duplicate active sessions
    existing = await db.execute(
        select(EntrySession).where(
            EntrySession.subscription_id == sub.id,
            EntrySession.status == EntrySessionStatus.active,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya hay una sesión de entrada activa")

    from app.services.runtime_config import int_param
    minutes = body.duration_minutes or await int_param("sec_entry_default_minutes")
    session_body = EntrySessionCreate(
        subscription_id=sub.id,
        duration_minutes=max(1, min(minutes, 30)),
    )
    session = await start_entry_session(db=db, body=session_body, activated_by_user_id=None)
    return {
        "session_id": session.id,
        "expires_at": session.expires_at.isoformat(),
        "duration_minutes": session.duration_minutes,
        "status": session.status.value if hasattr(session.status, "value") else session.status,
    }


class VacationRequest(BaseModel):
    start_date: str       # YYYY-MM-DD
    end_date: str         # YYYY-MM-DD
    notes: Optional[str] = None
    token: Optional[str] = None  # portal token for non-IP clients


async def _resolve_portal_subscription(
    token: Optional[str], request: Request, db: AsyncSession, allow_device: bool = True
):
    """
    Resolve the security subscription, in this order:
    1. Mobile app device credential (Authorization: Device <id>.<secret>)
    2. Portal token
    3. Client IP (internet clients)
    Raises 401/404 on failure.
    """
    if allow_device:
        from app.services.security.app_devices import authenticate_device
        auth = await authenticate_device(db, request.headers.get("Authorization"))
        if auth is not None:
            return auth[1]

    if token:
        from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
        from sqlalchemy.orm import selectinload as _sil
        res = await db.execute(
            select(SecuritySubscription)
            .options(_sil(SecuritySubscription.features))
            .where(
                SecuritySubscription.portal_token == token,
                SecuritySubscription.status == SecuritySubscriptionStatus.active,
            )
        )
        sub = res.scalar_one_or_none()
        if sub is None:
            raise HTTPException(status_code=404, detail="Enlace inválido o suscripción inactiva")
        return sub
    else:
        ip = _client_ip(request)
        client = await _get_client_by_ip(ip, db)
        if not client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        _, sub = await _get_security_subscription(client, db)
        if sub is None:
            raise HTTPException(status_code=404, detail="Sin suscripción de seguridad activa")
        return sub


@router.get("/security/vacation")
async def portal_get_vacation(
    request: Request,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Return the current or scheduled vacation mode for the client's subscription."""
    from datetime import date
    from app.models.security.contract import VacationMode

    sub = await _resolve_portal_subscription(token, request, db)

    result = await db.execute(
        select(VacationMode).where(
            VacationMode.subscription_id == sub.id,
            VacationMode.active == True,
            VacationMode.end_date >= date.today(),
        )
    )
    vm = result.scalar_one_or_none()
    return {
        "active": vm is not None,
        "start_date": vm.start_date.isoformat() if vm else None,
        "end_date": vm.end_date.isoformat() if vm else None,
        "vacation_mode_enabled": sub.has_feature("vacation_mode"),
    }


@router.post("/security/vacation")
async def portal_activate_vacation(
    body: VacationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Client activates vacation mode from the portal."""
    from datetime import date
    from app.services.security.vacation import VacationModeCreate, create_vacation_mode

    sub = await _resolve_portal_subscription(body.token, request, db)

    if not sub.has_feature("vacation_mode"):
        raise HTTPException(status_code=403, detail="Modo ausencia no está habilitado en tu plan")

    vm_data = VacationModeCreate(
        subscription_id=sub.id,
        start_date=date.fromisoformat(body.start_date),
        end_date=date.fromisoformat(body.end_date),
        notes=body.notes,
    )
    vm = await create_vacation_mode(db, vm_data, created_by_user_id=None)
    return {
        "id": vm.id,
        "start_date": vm.start_date.isoformat(),
        "end_date": vm.end_date.isoformat(),
        "active": vm.active,
    }


class VacationCancelRequest(BaseModel):
    pin: str
    token: Optional[str] = None


@router.post("/security/vacation/cancel")
async def portal_cancel_vacation(
    body: VacationCancelRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Client cancels their vacation mode from the portal. Requires the alarm PIN.
    A duress PIN cancels normally (so a coercer sees nothing unusual) but raises
    a silent DURESS alert to the monitoring central.
    """
    from datetime import date, datetime, timezone
    from app.models.security.alert import SecurityAlert, SecurityAlertStatus, SecurityAlertType
    from app.models.security.contract import VacationMode
    from app.models.security.pin import PinType
    from app.services.security.notifications import dispatch_alert
    from app.services.security.pins import verify_owner_pin
    from app.services.security.vacation import cancel_vacation_mode

    sub = await _resolve_portal_subscription(body.token, request, db)

    result = await db.execute(
        select(VacationMode).where(
            VacationMode.subscription_id == sub.id,
            VacationMode.active == True,
            VacationMode.end_date >= date.today(),
        )
    )
    vm = result.scalar_one_or_none()
    if vm is None:
        raise HTTPException(status_code=404, detail="No hay modo ausencia activo")

    pin_type = await verify_owner_pin(db, sub.id, body.pin)
    cancelled = await cancel_vacation_mode(db, vm.id, source="portal")

    if pin_type == PinType.duress:
        alert = SecurityAlert(
            subscription_id=sub.id,
            alert_type=SecurityAlertType.DURESS,
            status=SecurityAlertStatus.new,
            triggered_at=datetime.now(timezone.utc),
            idempotency_key=f"duress_vacation_cancel:{vm.id}",
            operator_notes="PIN de coacción usado para cancelar el modo ausencia desde el portal",
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        await dispatch_alert(alert, db)

    return {"cancelled": True, "id": cancelled.id}


# ── Electronic contract ───────────────────────────────────────────────────────

@router.get("/security/contract")
async def portal_get_contract(
    request: Request,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Active contract text and whether this subscription already accepted it."""
    from app.services.security.contracts import get_acceptance, get_active_template

    sub = await _resolve_portal_subscription(token, request, db)
    if not sub.has_feature("digital_contract"):
        return {"enabled": False}

    tpl = await get_active_template(db)
    if tpl is None:
        return {"enabled": True, "template": None, "accepted": None}

    acc = await get_acceptance(db, sub.id, tpl.version)
    return {
        "enabled": True,
        "template": {
            "version": tpl.version,
            "title": tpl.title,
            "body": tpl.body,
            "body_hash": tpl.body_hash,
        },
        "accepted": {
            "accepted_at": acc.accepted_at,
            "signer_name": acc.signer_name,
            "has_pdf": bool(acc.pdf_path),
        } if acc else None,
    }


@router.post("/security/contract/accept")
async def portal_accept_contract(
    body: ContractAcceptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept the active contract. Identity is confirmed with the alarm PIN.
    A duress PIN records the acceptance normally but raises a silent DURESS alert.
    """
    from datetime import datetime, timezone
    from app.models.security.alert import SecurityAlert, SecurityAlertStatus, SecurityAlertType
    from app.models.security.pin import PinType
    from app.services.security.contracts import accept_contract
    from app.services.security.notifications import dispatch_alert
    from app.services.security.pins import verify_owner_pin

    sub = await _resolve_portal_subscription(body.token, request, db)
    if not sub.has_feature("digital_contract"):
        raise HTTPException(status_code=403, detail="El contrato electrónico no está habilitado en tu plan")

    pin_type = await verify_owner_pin(db, sub.id, body.pin)
    acc = await accept_contract(
        db, sub.id, body,
        ip=_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )

    if pin_type == PinType.duress:
        alert = SecurityAlert(
            subscription_id=sub.id,
            alert_type=SecurityAlertType.DURESS,
            status=SecurityAlertStatus.new,
            triggered_at=datetime.now(timezone.utc),
            idempotency_key=f"duress_contract:{acc.id}",
            operator_notes="PIN de coacción usado al firmar el contrato desde el portal",
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        await dispatch_alert(alert, db)

    return {"accepted_at": acc.accepted_at, "version": acc.version, "signer_name": acc.signer_name}


@router.get("/security/contract/pdf")
async def portal_contract_pdf(
    request: Request,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Download the client's own signed copy of the active contract."""
    from pathlib import Path
    from fastapi.responses import FileResponse
    from app.services.security.contracts import get_acceptance, get_active_template

    sub = await _resolve_portal_subscription(token, request, db)
    tpl = await get_active_template(db)
    acc = await get_acceptance(db, sub.id, tpl.version) if tpl else None
    if acc is None or not acc.pdf_path or not Path(acc.pdf_path).is_file():
        raise HTTPException(status_code=404, detail="No hay contrato firmado para descargar")
    return FileResponse(
        acc.pdf_path,
        media_type="application/pdf",
        filename=f"contrato_v{acc.version}.pdf",
    )
