from typing import List

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_db, require_admin
from app.schemas.security.subscription import SecurityPlanCreate, SecurityPlanResponse, SecurityPlanUpdate
from app.services.security.plans import create_plan, get_plan, list_plans, update_plan

router = APIRouter()


@router.get("/", response_model=List[SecurityPlanResponse])
async def list_security_plans(
    active_only: bool = Query(default=True),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await list_plans(db, active_only=active_only)


@router.get("/{plan_id}", response_model=SecurityPlanResponse)
async def get_security_plan(
    plan_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await get_plan(db, plan_id)


@router.post("/", response_model=SecurityPlanResponse, status_code=201)
async def create_security_plan(
    body: SecurityPlanCreate,
    _=Depends(require_admin),
    db=Depends(get_db),
):
    return await create_plan(db, body)


@router.patch("/{plan_id}", response_model=SecurityPlanResponse)
async def update_security_plan(
    plan_id: int,
    body: SecurityPlanUpdate,
    _=Depends(require_admin),
    db=Depends(get_db),
):
    return await update_plan(db, plan_id, body)
