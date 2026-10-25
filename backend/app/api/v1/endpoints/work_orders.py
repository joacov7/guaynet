from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.schemas.work_order import WorkOrderCreate, WorkOrderResponse, WorkOrderUpdate

router = APIRouter()


def _wo_to_response(wo: WorkOrder, client_name: Optional[str], assigned_name: Optional[str]) -> WorkOrderResponse:
    return WorkOrderResponse(
        id=wo.id,
        title=wo.title,
        description=wo.description,
        type=wo.type,
        status=wo.status,
        priority=wo.priority,
        client_id=wo.client_id,
        assigned_to_id=wo.assigned_to_id,
        scheduled_date=wo.scheduled_date,
        completed_at=wo.completed_at,
        address=wo.address,
        latitude=wo.latitude,
        longitude=wo.longitude,
        completion_notes=wo.completion_notes,
        photo_urls=wo.photo_urls,
        client_name=client_name,
        assigned_to_name=assigned_name,
        created_at=wo.created_at,
    )


async def _enrich(wo: WorkOrder, db: AsyncSession):
    client_name = None
    if wo.client_id:
        from app.models.client import Client
        c = await db.get(Client, wo.client_id)
        if c:
            client_name = f"{c.first_name} {c.last_name}"
    assigned_name = None
    if wo.assigned_to_id:
        from app.models.user import User
        u = await db.get(User, wo.assigned_to_id)
        if u:
            assigned_name = u.full_name or u.username
    return _wo_to_response(wo, client_name, assigned_name)


@router.get("/", response_model=List[WorkOrderResponse])
async def list_work_orders(
    status: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(WorkOrder)
    if status:
        q = q.where(WorkOrder.status == status)
    if assigned_to_id is not None:
        q = q.where(WorkOrder.assigned_to_id == assigned_to_id)
    q = q.order_by(WorkOrder.scheduled_date.asc().nullslast(), WorkOrder.created_at.desc())
    result = await db.execute(q)
    orders = result.scalars().all()
    return [await _enrich(wo, db) for wo in orders]


@router.post("/", response_model=WorkOrderResponse, status_code=201)
async def create_work_order(
    data: WorkOrderCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    wo = WorkOrder(**data.model_dump())
    db.add(wo)
    await db.commit()
    await db.refresh(wo)
    return await _enrich(wo, db)


@router.get("/{wo_id}", response_model=WorkOrderResponse)
async def get_work_order(
    wo_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return await _enrich(wo, db)


@router.put("/{wo_id}", response_model=WorkOrderResponse)
async def update_work_order(
    wo_id: int,
    data: WorkOrderUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(wo, k, v)
    if wo.status == WorkOrderStatus.completed and not wo.completed_at:
        wo.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(wo)
    return await _enrich(wo, db)


@router.delete("/{wo_id}", status_code=204)
async def delete_work_order(
    wo_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    await db.delete(wo)
    await db.commit()
