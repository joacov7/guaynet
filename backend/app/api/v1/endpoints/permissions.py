from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.models.permission import ROLES, SECTIONS, RolePermission
from app.models.user_permission import UserPermission
from app.schemas.permission import MyPermissions, RolePermissionResponse, RolePermissionUpdate

router = APIRouter()


# ── My permissions (used by frontend on login) ─────────────────────────────

@router.get("/my", response_model=MyPermissions)
async def my_permissions(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role == "admin" or current_user.is_superuser
    if is_admin:
        perms = {s: {"can_view": True, "can_edit": True} for s in SECTIONS}
        return MyPermissions(role="admin", is_admin=True, permissions=perms)

    # Role-level permissions
    role_rows = (await db.execute(
        select(RolePermission).where(RolePermission.role == current_user.role)
    )).scalars().all()
    perms = {r.section: {"can_view": r.can_view, "can_edit": r.can_edit} for r in role_rows}

    # User-level overrides win over role
    user_rows = (await db.execute(
        select(UserPermission).where(UserPermission.user_id == current_user.id)
    )).scalars().all()
    for r in user_rows:
        perms[r.section] = {"can_view": r.can_view, "can_edit": r.can_edit}

    for s in SECTIONS:
        if s not in perms:
            perms[s] = {"can_view": False, "can_edit": False}

    return MyPermissions(role=current_user.role, is_admin=False, permissions=perms)


# ── Role permissions ────────────────────────────────────────────────────────

@router.get("/", response_model=List[RolePermissionResponse])
async def list_permissions(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(RolePermission).order_by(RolePermission.role, RolePermission.section)
    )).scalars().all()
    return rows


@router.put("/{role}/{section}", response_model=RolePermissionResponse)
async def update_permission(
    role: str,
    section: str,
    body: RolePermissionUpdate,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if role not in ROLES:
        raise HTTPException(400, f"Rol inválido. Válidos: {ROLES}")
    if section not in SECTIONS:
        raise HTTPException(400, f"Sección inválida. Válidas: {SECTIONS}")

    result = await db.execute(
        select(RolePermission).where(RolePermission.role == role, RolePermission.section == section)
    )
    perm = result.scalar_one_or_none()
    if not perm:
        perm = RolePermission(role=role, section=section)

    perm.can_view = body.can_view
    perm.can_edit = body.can_edit
    db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return perm


# ── User permissions ────────────────────────────────────────────────────────

class UserPermissionOut(BaseModel):
    section: str
    can_view: bool
    can_edit: bool
    is_override: bool

    class Config:
        from_attributes = True


class UserPermissionUpdate(BaseModel):
    can_view: bool
    can_edit: bool


@router.get("/users/{user_id}", response_model=List[UserPermissionOut])
async def get_user_permissions(
    user_id: int,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import User
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    # Role baseline
    role_rows = (await db.execute(
        select(RolePermission).where(RolePermission.role == user.role)
    )).scalars().all()
    role_map = {r.section: r for r in role_rows}

    # User overrides
    user_rows = (await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )).scalars().all()
    override_map = {r.section: r for r in user_rows}

    result = []
    for section in SECTIONS:
        if section in override_map:
            r = override_map[section]
            result.append(UserPermissionOut(section=section, can_view=r.can_view, can_edit=r.can_edit, is_override=True))
        elif section in role_map:
            r = role_map[section]
            result.append(UserPermissionOut(section=section, can_view=r.can_view, can_edit=r.can_edit, is_override=False))
        else:
            result.append(UserPermissionOut(section=section, can_view=False, can_edit=False, is_override=False))
    return result


@router.put("/users/{user_id}/{section}", response_model=UserPermissionOut)
async def set_user_permission(
    user_id: int,
    section: str,
    body: UserPermissionUpdate,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if section not in SECTIONS:
        raise HTTPException(400, f"Sección inválida")

    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id, UserPermission.section == section)
    )
    perm = result.scalar_one_or_none()
    if not perm:
        perm = UserPermission(user_id=user_id, section=section)

    perm.can_view = body.can_view
    perm.can_edit = body.can_edit
    db.add(perm)
    await db.commit()
    return UserPermissionOut(section=section, can_view=perm.can_view, can_edit=perm.can_edit, is_override=True)


@router.delete("/users/{user_id}/{section}", status_code=204)
async def delete_user_permission(
    user_id: int,
    section: str,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id, UserPermission.section == section)
    )
    perm = result.scalar_one_or_none()
    if perm:
        await db.delete(perm)
        await db.commit()
