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


async def create_plan(db: AsyncSession, body) -> SecurityPlan:
    data = body.model_dump()
    data["default_features"] = [f.value for f in body.default_features]
    plan = SecurityPlan(**data)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def update_plan(db: AsyncSession, plan_id: int, body) -> SecurityPlan:
    """Changes apply to new subscriptions; existing ones keep their own feature toggles."""
    plan = await get_plan(db, plan_id)
    changes = body.model_dump(exclude_unset=True)
    if "default_features" in changes and changes["default_features"] is not None:
        changes["default_features"] = [f.value for f in body.default_features]
    for field, value in changes.items():
        setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return plan
