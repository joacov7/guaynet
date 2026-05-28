from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.channel import Category, Channel
from app.models.user import User

router = APIRouter()


@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = (await db.execute(select(Category).order_by(Category.order, Category.name))).scalars().all()
    return [{"id": r.id, "name": r.name, "icon": r.icon} for r in rows]


@router.get("/channels")
async def list_channels(
    category_id: Optional[int] = None,
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = (
        select(Channel)
        .options(selectinload(Channel.category))
        .where(Channel.is_active == True)
        .order_by(Channel.order, Channel.name)
    )
    if category_id is not None:
        q = q.where(Channel.category_id == category_id)
    if search:
        q = q.where(Channel.name.ilike(f"%{search}%"))
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "logo_url": r.logo_url,
            "stream_url": r.stream_url,
            "category_id": r.category_id,
            "category_name": r.category.name if r.category else None,
        }
        for r in rows
    ]
