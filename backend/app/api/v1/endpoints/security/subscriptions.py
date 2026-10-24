"""
Subscriptions endpoints — Stage 2 implementation pending.
"""
from typing import List

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_db
from app.schemas.security.subscription import (
    SecurityFeatureToggle,
    SecuritySubscriptionCreate,
    SecuritySubscriptionResponse,
    SecuritySubscriptionUpdate,
)

router = APIRouter()


@router.get("/", response_model=List[SecuritySubscriptionResponse])
async def list_subscriptions(
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.post("/", response_model=SecuritySubscriptionResponse, status_code=201)
async def create_subscription(
    body: SecuritySubscriptionCreate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.get("/{subscription_id}", response_model=SecuritySubscriptionResponse)
async def get_subscription(
    subscription_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.patch("/{subscription_id}", response_model=SecuritySubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    body: SecuritySubscriptionUpdate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.post("/{subscription_id}/features", response_model=List[dict])
async def toggle_feature(
    subscription_id: int,
    body: SecurityFeatureToggle,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.get("/{subscription_id}/beat-status")
async def get_beat_status(
    subscription_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")
