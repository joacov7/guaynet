from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.device import SecurityDevice
from app.schemas.security.device import SecurityDeviceCreate, SecurityDeviceUpdate


async def list_devices(
    db: AsyncSession,
    subscription_id: int,
    active_only: bool = True,
) -> List[SecurityDevice]:
    q = select(SecurityDevice).where(SecurityDevice.subscription_id == subscription_id)
    if active_only:
        q = q.where(SecurityDevice.is_active == True)
    result = await db.execute(q.order_by(SecurityDevice.id))
    return result.scalars().all()


async def get_device(db: AsyncSession, device_id: int) -> SecurityDevice:
    device = await db.get(SecurityDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return device


async def create_device(db: AsyncSession, body: SecurityDeviceCreate) -> SecurityDevice:
    device = SecurityDevice(**body.model_dump())
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


async def update_device(
    db: AsyncSession, device_id: int, body: SecurityDeviceUpdate
) -> SecurityDevice:
    device = await get_device(db, device_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    await db.commit()
    await db.refresh(device)
    return device
