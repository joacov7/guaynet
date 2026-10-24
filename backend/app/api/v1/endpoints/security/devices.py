from typing import List

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_db
from app.schemas.security.device import (
    DeviceZoneBase,
    SecurityDeviceCreate,
    SecurityDeviceResponse,
    SecurityDeviceUpdate,
)
from app.services.security import devices as svc

router = APIRouter()


@router.get("/", response_model=List[SecurityDeviceResponse])
async def list_devices(
    subscription_id: int = Query(...),
    active_only: bool = Query(default=True),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.list_devices(db, subscription_id, active_only=active_only)


@router.post("/", response_model=SecurityDeviceResponse, status_code=201)
async def create_device(
    body: SecurityDeviceCreate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.create_device(db, body)


@router.get("/{device_id}", response_model=SecurityDeviceResponse)
async def get_device(
    device_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.get_device(db, device_id)


@router.patch("/{device_id}", response_model=SecurityDeviceResponse)
async def update_device(
    device_id: int,
    body: SecurityDeviceUpdate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.update_device(db, device_id, body)


@router.put("/{device_id}/zones", response_model=SecurityDeviceResponse)
async def replace_device_zones(
    device_id: int,
    body: List[DeviceZoneBase],
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.replace_zones(db, device_id, body)
