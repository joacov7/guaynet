from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.alert import SecurityAlert, SecurityAlertStatus
from app.schemas.security.alert import SecurityAlertUpdate


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
