from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.client import Client
from app.models.plan import Plan
from app.schemas.plan import PlanCreate, PlanResponse, PlanUpdate

router = APIRouter()


async def _plan_response(plan: Plan, db: AsyncSession) -> PlanResponse:
    count_result = await db.execute(select(func.count()).where(Client.plan_id == plan.id))
    count = count_result.scalar_one()
    data = PlanResponse.model_validate(plan)
    data.client_count = count
    return data


@router.get("/", response_model=List[PlanResponse])
async def list_plans(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Plan)
    if active_only:
        q = q.where(Plan.is_active == True)
    result = await db.execute(q.order_by(Plan.price))
    plans = result.scalars().all()
    return [await _plan_response(p, db) for p in plans]


@router.post("/", response_model=PlanResponse, status_code=201)
async def create_plan(
    body: PlanCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan = Plan(**body.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return await _plan_response(plan, db)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return await _plan_response(plan, db)


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int,
    body: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return await _plan_response(plan, db)


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    count_result = await db.execute(select(func.count()).where(Client.plan_id == plan_id))
    if count_result.scalar_one() > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar un plan con clientes activos")

    await db.delete(plan)
    await db.commit()
