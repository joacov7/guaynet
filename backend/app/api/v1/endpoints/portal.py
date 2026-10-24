"""
Client self-service portal.
Clients are identified by their source IP address — no password required
(the ISP controls the network, so IP ≡ identity on the local network).
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.plan import Plan

router = APIRouter()

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

@router.get("/me")
async def portal_me(request: Request, db: AsyncSession = Depends(get_db)):
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

@router.get("/security/token/{token}")
async def portal_security_by_token(token: str, db: AsyncSession = Depends(get_db)):
    """
    Return the client's security data identified by their portal token.
    Used by clients who don't have internet service with Guaynet.
    """
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
    from app.models.security.property import Property
    from app.models.security.event import SecurityEvent
    from app.models.security.alert import SecurityAlert
    from app.models.security.report import SecurityMonthlyReport

    result = await db.execute(
        select(SecuritySubscription)
        .options(
            selectinload(SecuritySubscription.plan),
            selectinload(SecuritySubscription.features),
        )
        .where(
            SecuritySubscription.portal_token == token,
            SecuritySubscription.status == SecuritySubscriptionStatus.active,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Enlace inválido o suscripción inactiva")

    prop_result = await db.execute(select(Property).where(Property.id == sub.property_id))
    prop = prop_result.scalar_one_or_none()

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
            "plan_name": sub.plan.name if sub.plan else "—",
            "beat_account_id": sub.beat_account_id,
            "property_name": prop.name if prop else "—",
            "property_address": prop.address if prop else "—",
            "entry_secure_enabled": sub.has_feature("entry_secure"),
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
    from datetime import datetime, timezone
    from sqlalchemy import select, func
    from app.models.security.event import SecurityEvent
    from app.models.security.alert import SecurityAlert
    from app.models.security.report import SecurityMonthlyReport

    ip = _client_ip(request)
    client = await _get_client_by_ip(ip, db)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado para esta IP")

    prop, sub = await _get_security_subscription(client, db)
    if sub is None:
        return {"has_subscription": False}

    # Recent events (last 5)
    events_result = await db.execute(
        select(SecurityEvent)
        .where(SecurityEvent.subscription_id == sub.id)
        .order_by(SecurityEvent.occurred_at.desc())
        .limit(5)
    )
    events = events_result.scalars().all()

    # Active alert count
    alerts_result = await db.execute(
        select(func.count()).select_from(SecurityAlert).where(
            SecurityAlert.subscription_id == sub.id,
            SecurityAlert.status.in_(["new", "acknowledged"]),
        )
    )
    active_alerts = alerts_result.scalar() or 0

    # Last monthly report
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
            "plan_name": sub.plan.name if sub.plan else "—",
            "beat_account_id": sub.beat_account_id,
            "property_name": prop.name if prop else "—",
            "property_address": prop.address if prop else "—",
            "entry_secure_enabled": sub.has_feature("entry_secure"),
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


class EntrySessionRequest(BaseModel):
    duration_minutes: int = 5
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

    # Resolve subscription: by portal token (security-only clients) or by IP
    if body.token:
        from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
        from sqlalchemy.orm import selectinload as _sil
        res = await db.execute(
            select(SecuritySubscription)
            .options(_sil(SecuritySubscription.features))
            .where(
                SecuritySubscription.portal_token == body.token,
                SecuritySubscription.status == SecuritySubscriptionStatus.active,
            )
        )
        sub = res.scalar_one_or_none()
        if sub is None:
            raise HTTPException(status_code=404, detail="Enlace inválido o suscripción inactiva")
    else:
        ip = _client_ip(request)
        client = await _get_client_by_ip(ip, db)
        if not client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        _, sub = await _get_security_subscription(client, db)
        if sub is None:
            raise HTTPException(status_code=404, detail="Sin suscripción de seguridad activa")

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

    session_body = EntrySessionCreate(
        subscription_id=sub.id,
        duration_minutes=max(1, min(body.duration_minutes, 30)),
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


async def _resolve_portal_subscription(token: Optional[str], request: Request, db: AsyncSession):
    """Resolve the security subscription from token or IP. Raises 404 on failure."""
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
