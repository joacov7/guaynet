from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.security.subscription import SecuritySubscription
from app.services.security import schedule as svc
from app.services.security.schedule import ScheduleDay, ScheduleDayResponse

router = APIRouter()


async def _require_subscription(db: AsyncSession, subscription_id: int) -> None:
    if await db.get(SecuritySubscription, subscription_id) is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")


@router.get("/{subscription_id}/schedule", response_model=List[ScheduleDayResponse])
async def get_schedule(
    subscription_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_subscription(db, subscription_id)
    return [ScheduleDayResponse.model_validate(r, from_attributes=True) for r in await svc.get_schedule(db, subscription_id)]


@router.put("/{subscription_id}/schedule", response_model=List[ScheduleDayResponse])
async def replace_schedule(
    subscription_id: int,
    body: List[ScheduleDay],
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace the weekly schedule. Weekdays not sent are treated as closed days."""
    await _require_subscription(db, subscription_id)
    rows = await svc.replace_schedule(db, subscription_id, body)
    return [ScheduleDayResponse.model_validate(r, from_attributes=True) for r in rows]
