"""
Security dashboard — single endpoint that returns all stats needed by the
operator dashboard page. Uses efficient aggregate queries to avoid N+1 calls.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db

router = APIRouter()


@router.get("/")
async def security_dashboard(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.security.alert import SecurityAlert, SecurityAlertStatus, SecurityAlertType
    from app.models.security.contract import VacationMode
    from app.models.security.entry_session import EntrySession, EntrySessionStatus
    from app.models.security.event import SecurityEvent
    from app.models.security.property import Property
    from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
    from app.models.security.subscription import SecurityPlan

    now = datetime.now(timezone.utc)
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Subscription counts ───────────────────────────────────────────────────
    sub_counts_result = await db.execute(
        select(SecuritySubscription.status, func.count().label("cnt"))
        .group_by(SecuritySubscription.status)
    )
    sub_counts = {row.status: row.cnt for row in sub_counts_result.all()}
    active_subs = sub_counts.get(SecuritySubscriptionStatus.active, 0)
    suspended_subs = sub_counts.get(SecuritySubscriptionStatus.suspended, 0)
    pending_subs = sub_counts.get(SecuritySubscriptionStatus.pending_install, 0)

    # ── Alert counts ──────────────────────────────────────────────────────────
    alert_counts_result = await db.execute(
        select(SecurityAlert.status, func.count().label("cnt"))
        .group_by(SecurityAlert.status)
    )
    alert_counts = {row.status: row.cnt for row in alert_counts_result.all()}
    open_alerts_count = (
        alert_counts.get(SecurityAlertStatus.new, 0)
        + alert_counts.get(SecurityAlertStatus.acknowledged, 0)
    )

    alerts_today_result = await db.execute(
        select(func.count()).select_from(SecurityAlert).where(
            SecurityAlert.triggered_at >= now.replace(hour=0, minute=0, second=0, microsecond=0)
        )
    )
    alerts_today = alerts_today_result.scalar() or 0

    alerts_week_result = await db.execute(
        select(func.count()).select_from(SecurityAlert).where(
            SecurityAlert.triggered_at >= week_ago
        )
    )
    alerts_this_week = alerts_week_result.scalar() or 0

    # ── Active entry sessions ─────────────────────────────────────────────────
    active_sessions_result = await db.execute(
        select(func.count()).select_from(EntrySession).where(
            EntrySession.status == EntrySessionStatus.active
        )
    )
    active_sessions_count = active_sessions_result.scalar() or 0

    # ── Vacation modes active today ───────────────────────────────────────────
    vacation_result = await db.execute(
        select(func.count()).select_from(VacationMode).where(
            VacationMode.active == True,
            VacationMode.start_date <= today,
            VacationMode.end_date >= today,
        )
    )
    vacation_active_count = vacation_result.scalar() or 0

    # ── Alerts by day (last 7 days) ───────────────────────────────────────────
    day_counts_result = await db.execute(
        select(
            func.date_trunc("day", SecurityAlert.triggered_at).label("day"),
            func.count().label("cnt"),
        )
        .where(SecurityAlert.triggered_at >= week_ago)
        .group_by(func.date_trunc("day", SecurityAlert.triggered_at))
        .order_by(func.date_trunc("day", SecurityAlert.triggered_at))
    )
    day_counts_raw = {row.day.date(): row.cnt for row in day_counts_result.all()}
    alerts_by_day = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        alerts_by_day.append({"date": d.isoformat(), "count": day_counts_raw.get(d, 0)})

    # ── Alerts by type (last 30 days) ─────────────────────────────────────────
    type_counts_result = await db.execute(
        select(SecurityAlert.alert_type, func.count().label("cnt"))
        .where(SecurityAlert.triggered_at >= month_ago)
        .group_by(SecurityAlert.alert_type)
        .order_by(func.count().desc())
    )
    alerts_by_type = [
        {"type": row.alert_type, "count": row.cnt}
        for row in type_counts_result.all()
    ]

    # ── Open alerts with property context (latest 10) ─────────────────────────
    open_alerts_result = await db.execute(
        select(
            SecurityAlert,
            Property.name.label("property_name"),
            Property.address.label("property_address"),
        )
        .join(SecuritySubscription, SecuritySubscription.id == SecurityAlert.subscription_id)
        .join(Property, Property.id == SecuritySubscription.property_id)
        .where(SecurityAlert.status.in_(["new", "acknowledged"]))
        .order_by(
            case(
                (SecurityAlert.alert_type == SecurityAlertType.PANIC, 0),
                (SecurityAlert.alert_type == SecurityAlertType.DURESS, 1),
                (SecurityAlert.alert_type == SecurityAlertType.INTRUSION, 2),
                else_=3,
            ).asc(),
            SecurityAlert.triggered_at.asc(),
        )
        .limit(10)
    )
    open_alerts = [
        {
            "id": a.id,
            "alert_type": a.alert_type.value if hasattr(a.alert_type, "value") else a.alert_type,
            "status": a.status.value if hasattr(a.status, "value") else a.status,
            "triggered_at": a.triggered_at.isoformat(),
            "subscription_id": a.subscription_id,
            "property_name": prop_name or "—",
            "property_address": prop_address or "—",
        }
        for a, prop_name, prop_address in open_alerts_result.all()
    ]

    # ── Active entry sessions with property context ───────────────────────────
    sessions_result = await db.execute(
        select(EntrySession, Property.name.label("property_name"))
        .join(SecuritySubscription, SecuritySubscription.id == EntrySession.subscription_id)
        .join(Property, Property.id == SecuritySubscription.property_id)
        .where(EntrySession.status == EntrySessionStatus.active)
        .order_by(EntrySession.expires_at.asc())
    )
    active_sessions = [
        {
            "id": s.id,
            "subscription_id": s.subscription_id,
            "expires_at": s.expires_at.isoformat(),
            "duration_minutes": s.duration_minutes,
            "property_name": prop_name or "—",
        }
        for s, prop_name in sessions_result.all()
    ]

    # ── Recent events across all subs (last 8) ────────────────────────────────
    events_result = await db.execute(
        select(SecurityEvent, Property.name.label("property_name"))
        .join(SecuritySubscription, SecuritySubscription.id == SecurityEvent.subscription_id)
        .join(Property, Property.id == SecuritySubscription.property_id)
        .order_by(SecurityEvent.occurred_at.desc())
        .limit(8)
    )
    from app.services.security.devices import zone_names_for

    event_rows = events_result.all()
    zone_names = await zone_names_for(db, {e.subscription_id for e, _ in event_rows})
    recent_events = [
        {
            "id": e.id,
            "event_type": e.event_type.value if hasattr(e.event_type, "value") else e.event_type,
            "occurred_at": e.occurred_at.isoformat(),
            "zone_number": e.zone_number,
            "zone_name": zone_names.get((e.subscription_id, e.zone_number)),
            "subscription_id": e.subscription_id,
            "property_name": prop_name or "—",
        }
        for e, prop_name in event_rows
    ]

    return {
        "stats": {
            "active_subscriptions": active_subs,
            "suspended_subscriptions": suspended_subs,
            "pending_subscriptions": pending_subs,
            "open_alerts": open_alerts_count,
            "new_alerts": alert_counts.get(SecurityAlertStatus.new, 0),
            "acknowledged_alerts": alert_counts.get(SecurityAlertStatus.acknowledged, 0),
            "active_entry_sessions": active_sessions_count,
            "vacation_active": vacation_active_count,
            "alerts_today": alerts_today,
            "alerts_this_week": alerts_this_week,
        },
        "open_alerts": open_alerts,
        "active_entry_sessions": active_sessions,
        "recent_events": recent_events,
        "alerts_by_day": alerts_by_day,
        "alerts_by_type": alerts_by_type,
    }
