from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_db
from app.schemas.security.property import PropertyCreate, PropertyResponse, PropertyUpdate
from app.services.security import properties as svc

router = APIRouter()


@router.get("/", response_model=List[PropertyResponse])
async def list_properties(
    owner_user_id: Optional[int] = Query(default=None),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.list_properties(db, owner_user_id=owner_user_id)


@router.post("/", response_model=PropertyResponse, status_code=201)
async def create_property(
    body: PropertyCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if body.owner_user_id is None:
        body.owner_user_id = current_user.id
    return await svc.create_property(db, body)


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.get_property(db, property_id)


@router.patch("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    body: PropertyUpdate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.update_property(db, property_id, body)
