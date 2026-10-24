from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.security.neighborhood import SecurityNeighborhoodGroup, SecurityNeighborhoodMembership

router = APIRouter()


class NeighborhoodGroupCreate(BaseModel):
    name: str
    telegram_group_id: str
    description: Optional[str] = None


class NeighborhoodGroupResponse(BaseModel):
    id: int
    name: str
    telegram_group_id: str
    description: Optional[str]

    class Config:
        from_attributes = True


class NeighborhoodGroupWithCount(NeighborhoodGroupResponse):
    member_count: int


class MembershipCreate(BaseModel):
    subscription_id: int


class MembershipResponse(BaseModel):
    id: int
    group_id: int
    subscription_id: int

    class Config:
        from_attributes = True


@router.get("", response_model=List[NeighborhoodGroupWithCount])
async def list_groups(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SecurityNeighborhoodGroup))
    groups = result.scalars().all()

    out = []
    for g in groups:
        count_result = await db.execute(
            select(SecurityNeighborhoodMembership).where(SecurityNeighborhoodMembership.group_id == g.id)
        )
        count = len(count_result.scalars().all())
        out.append(NeighborhoodGroupWithCount(
            id=g.id,
            name=g.name,
            telegram_group_id=g.telegram_group_id,
            description=g.description,
            member_count=count,
        ))
    return out


@router.post("", response_model=NeighborhoodGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: NeighborhoodGroupCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = SecurityNeighborhoodGroup(
        name=body.name,
        telegram_group_id=body.telegram_group_id,
        description=body.description,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.patch("/{group_id}", response_model=NeighborhoodGroupResponse)
async def update_group(
    group_id: int,
    body: NeighborhoodGroupCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SecurityNeighborhoodGroup).where(SecurityNeighborhoodGroup.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    group.name = body.name
    group.telegram_group_id = body.telegram_group_id
    group.description = body.description
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SecurityNeighborhoodGroup).where(SecurityNeighborhoodGroup.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    await db.delete(group)
    await db.commit()


@router.get("/{group_id}/members", response_model=List[MembershipResponse])
async def list_members(
    group_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SecurityNeighborhoodMembership).where(SecurityNeighborhoodMembership.group_id == group_id)
    )
    return result.scalars().all()


@router.post("/{group_id}/members", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    group_id: int,
    body: MembershipCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify group exists
    group_result = await db.execute(select(SecurityNeighborhoodGroup).where(SecurityNeighborhoodGroup.id == group_id))
    if group_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    # Check if subscription already belongs to a group
    existing = await db.execute(
        select(SecurityNeighborhoodMembership).where(
            SecurityNeighborhoodMembership.subscription_id == body.subscription_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="La suscripción ya pertenece a un grupo vecinal")

    membership = SecurityNeighborhoodMembership(group_id=group_id, subscription_id=body.subscription_id)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


@router.delete("/{group_id}/members/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: int,
    subscription_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SecurityNeighborhoodMembership).where(
            SecurityNeighborhoodMembership.group_id == group_id,
            SecurityNeighborhoodMembership.subscription_id == subscription_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Miembro no encontrado en este grupo")
    await db.delete(membership)
    await db.commit()
