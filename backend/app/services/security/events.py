from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.event import SecurityEvent, SecurityEventType


async def list_events(
    db: AsyncSession,
    subscription_id: int,
    limit: int = 50,
    event_type: Optional[SecurityEventType] = None,
) -> List[SecurityEvent]:
    q = (
        select(SecurityEvent)
        .where(SecurityEvent.subscription_id == subscription_id)
        .order_by(SecurityEvent.occurred_at.desc())
        .limit(limit)
    )
    if event_type is not None:
        q = q.where(SecurityEvent.event_type == event_type)
    result = await db.execute(q)
    return result.scalars().all()
