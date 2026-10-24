"""
Alerts endpoints — Stage 2 implementation pending.
"""
from typing import List

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_db
from app.schemas.security.alert import SecurityAlertResponse, SecurityAlertUpdate

router = APIRouter()


@router.get("/", response_model=List[SecurityAlertResponse])
async def list_alerts(
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.get("/{alert_id}", response_model=SecurityAlertResponse)
async def get_alert(
    alert_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.patch("/{alert_id}", response_model=SecurityAlertResponse)
async def update_alert(
    alert_id: int,
    body: SecurityAlertUpdate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")
