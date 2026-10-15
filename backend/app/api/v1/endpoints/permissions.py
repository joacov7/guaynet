from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.models.permission import ROLES, SECTIONS, RolePermission
from app.schemas.permission import MyPermissions, RolePermissionResponse, RolePermissionUpdate

router = APIRouter()


@router.get("/my", response_model=MyPermissions)
async def my_permissions(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role == "admin" or current_user.is_superuser
    if is_admin:
        perms = {s: {"can_view": True, "can_edit": True} for s in SECTIONS}
        return MyPermissions(role="admin", is_admin=True, permissions=perms)

    rows = (await db.execute(
        select(RolePermission).where(RolePermission.role == current_user.role)
    )).scalars().all()

    perms = {r.section: {"can_view": r.can_view, "can_edit": r.can_edit} for r in rows}
    # fill missing sections with no access
    for s in SECTIONS:
        if s not in perms:
            perms[s] = {"can_view": False, "can_edit": False}

    return MyPermissions(role=current_user.role, is_admin=False, permissions=perms)


@router.get("/", response_model=List[RolePermissionResponse])
async def list_permissions(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(RolePermission).order_by(RolePermission.role, RolePermission.section))).scalars().all()
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
