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


async def _check_internet_client(db: AsyncSession, client_id: Optional[int], property_id: Optional[int] = None) -> None:
    if client_id is None:
        return
    from app.models.client import Client
    if await db.get(Client, client_id) is None:
        raise HTTPException(status_code=404, detail="Cliente de internet no encontrado")
    # The IP portal resolves one property per client
    q = select(Property.id).where(Property.internet_client_id == client_id)
    if property_id is not None:
        q = q.where(Property.id != property_id)
    if (await db.execute(q)).first():
        raise HTTPException(status_code=409, detail="Ese cliente de internet ya está vinculado a otra propiedad")


async def create_property(db: AsyncSession, body: PropertyCreate) -> Property:
    await _check_internet_client(db, body.internet_client_id)
    prop = Property(**body.model_dump())
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return prop


async def update_property(
    db: AsyncSession, property_id: int, body: PropertyUpdate
) -> Property:
    prop = await get_property(db, property_id)
    changes = body.model_dump(exclude_unset=True)
    if "internet_client_id" in changes:
        await _check_internet_client(db, changes["internet_client_id"], property_id)
    for field, value in changes.items():
        setattr(prop, field, value)
    await db.commit()
    await db.refresh(prop)
    return prop
