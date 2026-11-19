from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from datetime import date
from typing import Optional

from app.core.deps import get_current_user, get_db
from app.services.security.vacation import (
    VacationModeCreate,
    list_vacation_modes,
    create_vacation_mode,
    cancel_vacation_mode,
    get_active_vacation,
)

router = APIRouter()


class VacationModeResponse(BaseModel):
    class Config:
        from_attributes = True
    id: int
    subscription_id: int
    start_date: date
    end_date: date
    notes: Optional[str] = None
    active: bool


@router.get("/", response_model=List[VacationModeResponse])
async def list_vacations(
    subscription_id: int = Query(...),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await list_vacation_modes(db, subscription_id)


@router.post("/", response_model=VacationModeResponse, status_code=201)
async def create_vacation(
    body: VacationModeCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await create_vacation_mode(db, body, created_by_user_id=current_user.id)


@router.post("/{vacation_id}/cancel", response_model=VacationModeResponse)
async def cancel_vacation(
    vacation_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await cancel_vacation_mode(db, vacation_id)
