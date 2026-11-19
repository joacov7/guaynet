from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.inventory import EquipmentCondition, EquipmentStatus, InventoryItem

router = APIRouter()


class ItemCreate(BaseModel):
    name: str
    category: str
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    quantity: int = 1
    unit_cost: Optional[float] = None
    condition: EquipmentCondition = EquipmentCondition.new
    status: EquipmentStatus = EquipmentStatus.in_stock
    client_id: Optional[int] = None
    notes: Optional[str] = None


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    quantity: Optional[int] = None
    unit_cost: Optional[float] = None
    condition: Optional[EquipmentCondition] = None
    status: Optional[EquipmentStatus] = None
    client_id: Optional[int] = None
    notes: Optional[str] = None


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    brand: Optional[str]
    model: Optional[str]
    serial_number: Optional[str]
    quantity: int
    unit_cost: Optional[float]
    condition: EquipmentCondition
    status: EquipmentStatus
    client_id: Optional[int]
    notes: Optional[str]
    created_at: str

    @classmethod
    def from_orm(cls, item: InventoryItem) -> "ItemResponse":
        return cls(
            id=item.id,
            name=item.name,
            category=item.category,
            brand=item.brand,
            model=item.model,
            serial_number=item.serial_number,
            quantity=item.quantity,
            unit_cost=float(item.unit_cost) if item.unit_cost is not None else None,
            condition=item.condition,
            status=item.status,
            client_id=item.client_id,
            notes=item.notes,
            created_at=item.created_at.isoformat(),
        )


@router.get("/", response_model=List[ItemResponse])
async def list_items(
    status: Optional[EquipmentStatus] = None,
    category: Optional[str] = None,
    client_id: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(default=200, le=1000),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(InventoryItem).order_by(InventoryItem.category, InventoryItem.name)
    if status:
        q = q.where(InventoryItem.status == status)
    if category:
        q = q.where(InventoryItem.category == category)
    if client_id is not None:
        q = q.where(InventoryItem.client_id == client_id)
    if search:
        like = f"%{search}%"
        q = q.where(
            InventoryItem.name.ilike(like)
            | InventoryItem.brand.ilike(like)
            | InventoryItem.model.ilike(like)
            | InventoryItem.serial_number.ilike(like)
        )
    result = await db.execute(q.offset(skip).limit(limit))
    return [ItemResponse.from_orm(i) for i in result.scalars().all()]


@router.get("/summary")
async def inventory_summary(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(InventoryItem.category, InventoryItem.status, func.count().label("count"), func.sum(InventoryItem.quantity).label("qty"))
        .group_by(InventoryItem.category, InventoryItem.status)
    )
    rows = result.all()
    return [{"category": r.category, "status": r.status, "count": r.count, "qty": r.qty} for r in rows]


@router.post("/", response_model=ItemResponse, status_code=201)
async def create_item(
    body: ItemCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    item = InventoryItem(**body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ItemResponse.from_orm(item)


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    item = await db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
    return ItemResponse.from_orm(item)


@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    body: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    item = await db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ItemResponse.from_orm(item)


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    item = await db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
    await db.delete(item)
    await db.commit()
