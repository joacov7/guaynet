from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.member import PropertyMember, EmergencyContact
from app.schemas.security.member import PropertyMemberCreate, PropertyMemberUpdate


async def list_members(
    db: AsyncSession,
    property_id: int,
    include_revoked: bool = False,
) -> List[PropertyMember]:
    q = select(PropertyMember).where(PropertyMember.property_id == property_id)
    if not include_revoked:
        q = q.where(PropertyMember.status == "active")
    result = await db.execute(q.order_by(PropertyMember.id))
    return result.scalars().all()


async def get_member(db: AsyncSession, member_id: int) -> PropertyMember:
    member = await db.get(PropertyMember, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    return member


async def create_member(db: AsyncSession, body: PropertyMemberCreate) -> PropertyMember:
    member = PropertyMember(**body.model_dump())
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def update_member(
    db: AsyncSession, member_id: int, body: PropertyMemberUpdate
) -> PropertyMember:
    member = await get_member(db, member_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    await db.commit()
    await db.refresh(member)
    return member


async def revoke_member(db: AsyncSession, member_id: int) -> PropertyMember:
    member = await get_member(db, member_id)
    member.status = "revoked"
    await db.commit()
    await db.refresh(member)
    return member
