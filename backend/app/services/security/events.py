from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.event import SecurityEvent, SecurityEventType


async def list_events(
    db: AsyncSession,
    subscription_id: int,
    limit: int = 200,
    event_type: Optional[SecurityEventType] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> List[SecurityEvent]:
    q = (
        select(SecurityEvent)
        .where(SecurityEvent.subscription_id == subscription_id)
        .order_by(SecurityEvent.occurred_at.desc())
        .limit(limit)
    )
    if event_type is not None:
        q = q.where(SecurityEvent.event_type == event_type)
    if from_date is not None:
        q = q.where(SecurityEvent.occurred_at >= from_date)
    if to_date is not None:
        q = q.where(SecurityEvent.occurred_at <= to_date)
    result = await db.execute(q)
    return result.scalars().all()
