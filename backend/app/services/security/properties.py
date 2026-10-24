from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.property import Property
from app.schemas.security.property import PropertyCreate, PropertyUpdate


async def list_properties(
    db: AsyncSession,
    owner_user_id: Optional[int] = None,
) -> List[Property]:
    q = select(Property).order_by(Property.id.desc())
    if owner_user_id is not None:
        q = q.where(Property.owner_user_id == owner_user_id)
    result = await db.execute(q)
    return result.scalars().all()


async def get_property(db: AsyncSession, property_id: int) -> Property:
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    return prop


async def create_property(db: AsyncSession, body: PropertyCreate) -> Property:
    prop = Property(**body.model_dump())
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return prop


async def update_property(
    db: AsyncSession, property_id: int, body: PropertyUpdate
) -> Property:
    prop = await get_property(db, property_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(prop, field, value)
    await db.commit()
    await db.refresh(prop)
    return prop
