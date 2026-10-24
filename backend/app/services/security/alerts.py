from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.alert import SecurityAlert, SecurityAlertStatus, SecurityAlertType
from app.schemas.security.alert import AlertPanelItem, SecurityAlertUpdate


async def list_panel_alerts(db: AsyncSession, limit: int = 100) -> List[AlertPanelItem]:
    """Active alerts (new + acknowledged) enriched with property/subscription context."""
    from app.models.security.subscription import SecuritySubscription
    from app.models.security.property import Property
    from app.models.security.plan import SecurityPlan
    from app.models.security.event import SecurityEvent
    from app.services.security.devices import zone_names_for

    priority = case(
        (SecurityAlert.alert_type == SecurityAlertType.PANIC, 0),
        (SecurityAlert.alert_type == SecurityAlertType.DURESS, 1),
        (SecurityAlert.alert_type == SecurityAlertType.INTRUSION, 2),
        else_=3,
    )

    result = await db.execute(
        select(
            SecurityAlert,
            Property.name.label("property_name"),
            Property.address.label("property_address"),
            SecuritySubscription.beat_account_id.label("beat_account_id"),
            SecurityPlan.name.label("plan_name"),
            SecurityEvent.zone_number.label("zone_number"),
        )
        .join(SecuritySubscription, SecuritySubscription.id == SecurityAlert.subscription_id)
        .join(Property, Property.id == SecuritySubscription.property_id)
        .outerjoin(SecurityPlan, SecurityPlan.id == SecuritySubscription.plan_id)
        .outerjoin(SecurityEvent, SecurityEvent.id == SecurityAlert.source_event_id)
        .where(SecurityAlert.status.in_(["new", "acknowledged"]))
        .order_by(priority.asc(), SecurityAlert.triggered_at.asc())
        .limit(limit)
    )

    rows = result.all()
    zone_names = await zone_names_for(db, {r[0].subscription_id for r in rows})

    return [
        AlertPanelItem(
            id=alert.id,
            alert_type=alert.alert_type,
            status=alert.status,
            triggered_at=alert.triggered_at,
            acknowledged_at=alert.acknowledged_at,
            operator_notes=alert.operator_notes,
            confirmation_sent_at=alert.confirmation_sent_at,
            confirmation_expires_at=alert.confirmation_expires_at,
            subscription_id=alert.subscription_id,
            beat_account_id=beat_account_id,
            property_name=property_name or "—",
            property_address=property_address or "—",
            plan_name=plan_name or "—",
            zone_number=zone_number,
            zone_name=zone_names.get((alert.subscription_id, zone_number)) if zone_number is not None else None,
        )
        for alert, property_name, property_address, beat_account_id, plan_name, zone_number in rows
    ]


async def list_alerts(
    db: AsyncSession,
    subscription_id: Optional[int] = None,
    status: Optional[SecurityAlertStatus] = None,
    limit: int = 50,
) -> List[SecurityAlert]:
    q = select(SecurityAlert).order_by(SecurityAlert.triggered_at.desc()).limit(limit)
    if subscription_id is not None:
        q = q.where(SecurityAlert.subscription_id == subscription_id)
    if status is not None:
        q = q.where(SecurityAlert.status == status)
    result = await db.execute(q)
    return result.scalars().all()


async def get_alert(db: AsyncSession, alert_id: int) -> SecurityAlert:
    alert = await db.get(SecurityAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return alert


async def update_alert(
    db: AsyncSession,
    alert_id: int,
    body: SecurityAlertUpdate,
    operator_user_id: int,
) -> SecurityAlert:
    alert = await get_alert(db, alert_id)
    now = datetime.now(timezone.utc)

    alert.status = body.status
    if body.operator_notes is not None:
        alert.operator_notes = body.operator_notes
    alert.operator_id = operator_user_id

    if body.status == SecurityAlertStatus.acknowledged and alert.acknowledged_at is None:
        alert.acknowledged_at = now
    elif body.status in (SecurityAlertStatus.resolved, SecurityAlertStatus.false_alarm):
        if alert.acknowledged_at is None:
            alert.acknowledged_at = now
        alert.resolved_at = now

    await db.commit()
    await db.refresh(alert)
    return alert
