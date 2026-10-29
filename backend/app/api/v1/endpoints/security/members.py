from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

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


@router.post("/{member_id}/telegram-link")
async def telegram_link_member(
    member_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    """One-time link (48 h) for this member to receive the alarm notices on Telegram."""
    from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
    from app.services.security.telegram_link import create_link

    member = await svc.get_member(db, member_id)
    sub = (await db.execute(
        select(SecuritySubscription)
        .where(
            SecuritySubscription.property_id == member.property_id,
            SecuritySubscription.status != SecuritySubscriptionStatus.cancelled,
        )
        .order_by(SecuritySubscription.id.desc())
    )).scalars().first()
    if sub is None:
        raise HTTPException(status_code=404, detail="La propiedad no tiene una suscripción de seguridad")
    return await create_link(db, sub.id, member_id)


@router.post("/{member_id}/telegram-unlink", response_model=PropertyMemberResponse)
async def telegram_unlink_member(
    member_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    from app.services.security.telegram_link import unlink_member
    return await unlink_member(db, member_id)
