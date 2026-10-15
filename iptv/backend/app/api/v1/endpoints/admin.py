import random
import string
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models.channel import Category, Channel
from app.models.user import User
from app.services.m3u_parser import parse_m3u

router = APIRouter()


def _gen_code(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    rows = (await db.execute(select(Category).order_by(Category.order))).scalars().all()
    return [{"id": r.id, "name": r.name, "icon": r.icon, "order": r.order} for r in rows]


class CategoryBody(BaseModel):
    name: str
    icon: Optional[str] = None
    order: int = 0


@router.post("/categories", status_code=201)
async def create_category(body: CategoryBody, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    cat = Category(name=body.name, icon=body.icon, order=body.order)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "icon": cat.icon, "order": cat.order}


@router.put("/categories/{cat_id}")
async def update_category(cat_id: int, body: CategoryBody, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    cat = await db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404)
    cat.name = body.name
    cat.icon = body.icon
    cat.order = body.order
    db.add(cat)
    await db.commit()
    return {"id": cat.id, "name": cat.name, "icon": cat.icon, "order": cat.order}


@router.delete("/categories/{cat_id}", status_code=204)
async def delete_category(cat_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    cat = await db.get(Category, cat_id)
    if cat:
        await db.delete(cat)
        await db.commit()


# ── Channels ──────────────────────────────────────────────────────────────────

@router.get("/channels")
async def list_channels(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    rows = (await db.execute(select(Channel).order_by(Channel.order, Channel.name))).scalars().all()
    return [
        {"id": r.id, "name": r.name, "logo_url": r.logo_url, "stream_url": r.stream_url,
         "category_id": r.category_id, "is_active": r.is_active, "order": r.order}
        for r in rows
    ]


class ChannelBody(BaseModel):
    name: str
    stream_url: str
    logo_url: Optional[str] = None
    category_id: Optional[int] = None
    is_active: bool = True
    order: int = 0


@router.post("/channels", status_code=201)
async def create_channel(body: ChannelBody, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    ch = Channel(**body.model_dump())
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    return {"id": ch.id, "name": ch.name}


@router.put("/channels/{ch_id}")
async def update_channel(ch_id: int, body: ChannelBody, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    ch = await db.get(Channel, ch_id)
    if not ch:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(ch, k, v)
    db.add(ch)
    await db.commit()
    return {"id": ch.id, "name": ch.name}


@router.delete("/channels/{ch_id}", status_code=204)
async def delete_channel(ch_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    ch = await db.get(Channel, ch_id)
    if ch:
        await db.delete(ch)
        await db.commit()


# ── M3U Import ────────────────────────────────────────────────────────────────

@router.post("/import/url")
async def import_from_url(
    url: str = Form(...),
    replace: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
    except Exception as e:
        raise HTTPException(400, f"No se pudo descargar la lista: {e}")
    return await _do_import(text, replace, db)


@router.post("/import/file")
async def import_from_file(
    file: UploadFile = File(...),
    replace: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    return await _do_import(text, replace, db)


async def _do_import(text: str, replace: bool, db: AsyncSession):
    channels = parse_m3u(text)
    if not channels:
        raise HTTPException(400, "No se encontraron canales en la lista")

    if replace:
        rows = (await db.execute(select(Channel))).scalars().all()
        for ch in rows:
            await db.delete(ch)
        await db.commit()

    # Auto-create categories
    cat_cache: dict = {}
    existing_cats = (await db.execute(select(Category))).scalars().all()
    for c in existing_cats:
        cat_cache[c.name.lower()] = c.id

    added = 0
    for item in channels:
        group = item.get("group") or "Sin categoría"
        key = group.lower()
        if key not in cat_cache:
            cat = Category(name=group)
            db.add(cat)
            await db.flush()
            cat_cache[key] = cat.id

        ch = Channel(
            name=item["name"],
            stream_url=item["stream_url"],
            logo_url=item.get("logo_url"),
            category_id=cat_cache[key],
        )
        db.add(ch)
        added += 1

    await db.commit()
    return {"imported": added, "categories": len(cat_cache)}


# ── Users / Access Codes ──────────────────────────────────────────────────────

@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    rows = (await db.execute(select(User).order_by(User.username))).scalars().all()
    return [
        {"id": r.id, "username": r.username, "role": r.role,
         "is_active": r.is_active, "access_code": r.access_code}
        for r in rows
    ]


class UserBody(BaseModel):
    username: str
    password: Optional[str] = None
    role: str = "viewer"
    generate_code: bool = True


@router.post("/users", status_code=201)
async def create_user(body: UserBody, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    dup = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if dup:
        raise HTTPException(400, "El nombre de usuario ya existe")
    user = User(
        username=body.username,
        hashed_password=hash_password(body.password) if body.password else None,
        role=body.role,
        access_code=_gen_code() if body.generate_code else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "username": user.username, "access_code": user.access_code}


@router.patch("/users/{user_id}/toggle")
async def toggle_user(user_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404)
    user.is_active = not user.is_active
    db.add(user)
    await db.commit()
    return {"is_active": user.is_active}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    user = await db.get(User, user_id)
    if user:
        await db.delete(user)
        await db.commit()
