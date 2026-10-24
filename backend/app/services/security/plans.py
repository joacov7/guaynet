from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.subscription import SecurityPlan


async def list_plans(db: AsyncSession, active_only: bool = True) -> List[SecurityPlan]:
    q = select(SecurityPlan).order_by(SecurityPlan.id)
    if active_only:
        q = q.where(SecurityPlan.is_active == True)
    result = await db.execute(q)
    return result.scalars().all()


async def get_plan(db: AsyncSession, plan_id: int) -> SecurityPlan:
    from fastapi import HTTPException
    plan = await db.get(SecurityPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return plan
