from collections import Counter
from typing import Dict, Iterable, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.security.device import DeviceZone, SecurityDevice
from app.schemas.security.device import DeviceZoneBase, SecurityDeviceCreate, SecurityDeviceUpdate


async def list_devices(
    db: AsyncSession,
    subscription_id: int,
    active_only: bool = True,
) -> List[SecurityDevice]:
    q = (
        select(SecurityDevice)
        .options(selectinload(SecurityDevice.zones))
        .where(SecurityDevice.subscription_id == subscription_id)
    )
    if active_only:
        q = q.where(SecurityDevice.is_active == True)
    result = await db.execute(q.order_by(SecurityDevice.id))
    return result.scalars().all()


async def get_device(db: AsyncSession, device_id: int) -> SecurityDevice:
    result = await db.execute(
        select(SecurityDevice)
        .options(selectinload(SecurityDevice.zones))
        .where(SecurityDevice.id == device_id)
        .execution_options(populate_existing=True)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return device


async def create_device(db: AsyncSession, body: SecurityDeviceCreate) -> SecurityDevice:
    device = SecurityDevice(**body.model_dump())
    db.add(device)
    await db.commit()
    return await get_device(db, device.id)


async def update_device(
    db: AsyncSession, device_id: int, body: SecurityDeviceUpdate
) -> SecurityDevice:
    device = await get_device(db, device_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    await db.commit()
    return await get_device(db, device_id)


async def replace_zones(
    db: AsyncSession, device_id: int, zones: List[DeviceZoneBase]
) -> SecurityDevice:
    """Replace the full zone list of a device (the panel's zone map)."""
    device = await get_device(db, device_id)

    dupes = [n for n, c in Counter(z.zone_number for z in zones).items() if c > 1]
    if dupes:
        raise HTTPException(
            status_code=422,
            detail=f"Número de zona repetido: {', '.join(map(str, sorted(dupes)))}",
        )

    # Zone numbers must be unique across the subscription: events from the
    # monitoring central only carry the zone number, not the device.
    others = await db.execute(
        select(DeviceZone.zone_number)
        .join(SecurityDevice, SecurityDevice.id == DeviceZone.device_id)
        .where(
            SecurityDevice.subscription_id == device.subscription_id,
            SecurityDevice.id != device.id,
            SecurityDevice.is_active == True,
        )
    )
    taken = {row[0] for row in others.all()} & {z.zone_number for z in zones}
    if taken:
        raise HTTPException(
            status_code=409,
            detail=f"Zona ya asignada a otro equipo de esta suscripción: {', '.join(map(str, sorted(taken)))}",
        )

    device.zones.clear()
    await db.flush()
    for z in zones:
        device.zones.append(DeviceZone(**z.model_dump()))
    await db.commit()
    return await get_device(db, device_id)


async def zone_names_for(
    db: AsyncSession, subscription_ids: Iterable[int]
) -> Dict[Tuple[int, int], str]:
    """Map (subscription_id, zone_number) → zone name, for active devices."""
    ids = set(subscription_ids)
    if not ids:
        return {}
    result = await db.execute(
        select(SecurityDevice.subscription_id, DeviceZone.zone_number, DeviceZone.zone_name)
        .join(DeviceZone, DeviceZone.device_id == SecurityDevice.id)
        .where(
            SecurityDevice.subscription_id.in_(ids),
            SecurityDevice.is_active == True,
            DeviceZone.zone_name.is_not(None),
        )
    )
    return {(sub_id, num): name for sub_id, num, name in result.all()}
