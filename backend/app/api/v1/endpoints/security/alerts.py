from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_db
from app.models.security.alert import SecurityAlertStatus
from app.schemas.security.alert import AlertPanelItem, SecurityAlertResponse, SecurityAlertUpdate
from app.services.security import alerts as svc

router = APIRouter()


@router.get("/panel", response_model=List[AlertPanelItem])
async def get_alert_panel(
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    """Active alerts enriched with property/subscription context for the operator panel."""
    return await svc.list_panel_alerts(db)


@router.get("/", response_model=List[SecurityAlertResponse])
async def list_alerts(
    subscription_id: Optional[int] = Query(default=None),
    status: Optional[SecurityAlertStatus] = Query(default=None),
    limit: int = Query(default=50, le=200),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.list_alerts(db, subscription_id=subscription_id, status=status, limit=limit)


@router.get("/{alert_id}", response_model=SecurityAlertResponse)
async def get_alert(
    alert_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.get_alert(db, alert_id)


@router.patch("/{alert_id}", response_model=SecurityAlertResponse)
async def update_alert(
    alert_id: int,
    body: SecurityAlertUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.update_alert(db, alert_id, body, operator_user_id=current_user.id)
