"""
Properties endpoints — Stage 2 implementation pending.
"""
from typing import List

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_db
from app.schemas.security.property import PropertyCreate, PropertyResponse, PropertyUpdate

router = APIRouter()


@router.get("/", response_model=List[PropertyResponse])
async def list_properties(
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.post("/", response_model=PropertyResponse, status_code=201)
async def create_property(
    body: PropertyCreate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.patch("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    body: PropertyUpdate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")
