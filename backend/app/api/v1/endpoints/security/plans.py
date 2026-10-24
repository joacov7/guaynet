from typing import List

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_db
from app.schemas.security.subscription import SecurityPlanResponse
from app.services.security.plans import list_plans, get_plan

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
