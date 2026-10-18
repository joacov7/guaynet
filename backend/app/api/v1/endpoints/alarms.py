from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.alarm import Alarm, AlarmStatus
from app.models.router import MikrotikRouter
from app.schemas.alarm import AlarmResponse

router = APIRouter()


async def _enrich(alarm: Alarm, db: AsyncSession) -> AlarmResponse:
    rt = await db.get(MikrotikRouter, alarm.router_id)
    return AlarmResponse(
        **{c.name: getattr(alarm, c.name) for c in Alarm.__table__.columns if hasattr(alarm, c.name)},
        router_name=rt.name if rt else None,
        router_host=rt.host if rt else None,
    )


@router.get("/", response_model=List[AlarmResponse])
async def list_alarms(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Alarm).order_by(desc(Alarm.triggered_at)).limit(limit)
    if status:
        q = q.where(Alarm.status == status)
    alarms = (await db.execute(q)).scalars().all()
    return [await _enrich(a, db) for a in alarms]


@router.get("/count-active")
async def count_active(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    count = await db.scalar(
        select(func.count(Alarm.id)).where(Alarm.status == AlarmStatus.active)
    )
    return {"count": count or 0}
