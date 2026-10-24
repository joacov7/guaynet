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
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
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

    ip = _client_ip(request)
    client = await _get_client_by_ip(ip, db)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    prop, sub = await _get_security_subscription(client, db)
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
    session = await start_entry_session(db=db, body=session_body, activated_by_user_id=0)
    return {
        "session_id": session.id,
        "expires_at": session.expires_at.isoformat(),
        "duration_minutes": session.duration_minutes,
        "status": session.status.value if hasattr(session.status, "value") else session.status,
    }
