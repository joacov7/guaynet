from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.client import Client
from app.models.zone import Zone
from app.schemas.zone import ZoneCreate, ZoneResponse, ZoneUpdate

router = APIRouter()


async def _zone_response(zone: Zone, db: AsyncSession) -> ZoneResponse:
    count_result = await db.execute(select(func.count()).where(Client.zone_id == zone.id))
    count = count_result.scalar_one()
    data = ZoneResponse.model_validate(zone)
    data.client_count = count
    return data


@router.get("/", response_model=List[ZoneResponse])
async def list_zones(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Zone).order_by(Zone.name))
    zones = result.scalars().all()
    return [await _zone_response(z, db) for z in zones]


@router.post("/", response_model=ZoneResponse, status_code=201)
async def create_zone(body: ZoneCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    zone = Zone(**body.model_dump())
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    return await _zone_response(zone, db)


@router.put("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: int,
    body: ZoneUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    return await _zone_response(zone, db)


@router.delete("/{zone_id}", status_code=204)
async def delete_zone(zone_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    count_result = await db.execute(select(func.count()).where(Client.zone_id == zone_id))
    if count_result.scalar_one() > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar una zona con clientes asignados")
    await db.delete(zone)
    await db.commit()
