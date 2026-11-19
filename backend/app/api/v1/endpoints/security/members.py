from typing import List

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_db
from app.schemas.security.member import PropertyMemberCreate, PropertyMemberResponse, PropertyMemberUpdate
from app.services.security import members as svc

router = APIRouter()


@router.get("/", response_model=List[PropertyMemberResponse])
async def list_members(
    property_id: int = Query(...),
    include_revoked: bool = Query(default=False),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.list_members(db, property_id, include_revoked=include_revoked)


@router.post("/", response_model=PropertyMemberResponse, status_code=201)
async def create_member(
    body: PropertyMemberCreate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.create_member(db, body)


@router.get("/{member_id}", response_model=PropertyMemberResponse)
async def get_member(
    member_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.get_member(db, member_id)


@router.patch("/{member_id}", response_model=PropertyMemberResponse)
async def update_member(
    member_id: int,
    body: PropertyMemberUpdate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.update_member(db, member_id, body)


@router.delete("/{member_id}", response_model=PropertyMemberResponse)
async def revoke_member(
    member_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.revoke_member(db, member_id)
