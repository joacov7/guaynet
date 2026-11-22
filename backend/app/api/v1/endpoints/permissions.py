from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import add_audit_log, get_current_user, get_db, require_admin
from app.models.permission import SECTIONS, Role, RolePermission
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


# ── Roles (defined by the admin) ─────────────────────────────────────────────

class RoleOut(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    users: int = 0


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    copy_from: Optional[str] = None  # start with the permissions of this role


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


# "admin" has full access; the others are paths of this router
_RESERVED_KEYS = {"admin", "roles", "users", "my"}


def _role_key(name: str, taken: set) -> str:
    """Short ASCII key from the name ("Atención al cliente" → "atencion_al_cliente")."""
    import re
    import unicodedata

    base = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")[:17] or "rol"
    key, n = base, 2
    while key in taken or key in _RESERVED_KEYS:
        key = f"{base[:17 - len(str(n))]}_{n}"
        n += 1
    return key


async def _get_role(db: AsyncSession, key: str) -> Role:
    role = await db.get(Role, key)
    if not role:
        raise HTTPException(404, "Rol no encontrado")
    return role


@router.get("/roles", response_model=List[RoleOut])
async def list_roles(_=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    from app.models.user import User

    counts = dict((await db.execute(select(User.role, func.count()).group_by(User.role))).all())
    roles = (await db.execute(select(Role).order_by(Role.name))).scalars().all()
    return [RoleOut(key=r.key, name=r.name, description=r.description, users=counts.get(r.key, 0)) for r in roles]


@router.post("/roles", response_model=RoleOut, status_code=201)
async def create_role(body: RoleCreate, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    name = body.name.strip()
    if not 2 <= len(name) <= 60:
        raise HTTPException(422, "El nombre del rol debe tener entre 2 y 60 caracteres")
    existing = (await db.execute(select(Role))).scalars().all()
    if any(r.name.lower() == name.lower() for r in existing):
        raise HTTPException(409, "Ya existe un rol con ese nombre")
    role = Role(key=_role_key(name, {r.key for r in existing}), name=name, description=(body.description or "").strip() or None)
    db.add(role)
    if body.copy_from:
        await _get_role(db, body.copy_from)
        for p in (await db.execute(select(RolePermission).where(RolePermission.role == body.copy_from))).scalars():
            db.add(RolePermission(role=role.key, section=p.section, can_view=p.can_view, can_edit=p.can_edit))
    add_audit_log(db, current_user, "create", "role", 0, name,
                  details=f"Rol nuevo{f' (copia de {body.copy_from})' if body.copy_from else ''}")
    await db.commit()
    return RoleOut(key=role.key, name=role.name, description=role.description, users=0)


@router.put("/roles/{key}", response_model=RoleOut)
async def update_role(key: str, body: RoleUpdate, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    role = await _get_role(db, key)
    old = role.name
    if body.name is not None:
        name = body.name.strip()
        if not 2 <= len(name) <= 60:
            raise HTTPException(422, "El nombre del rol debe tener entre 2 y 60 caracteres")
        clash = (await db.execute(select(Role).where(Role.key != key))).scalars().all()
        if any(r.name.lower() == name.lower() for r in clash):
            raise HTTPException(409, "Ya existe un rol con ese nombre")
        role.name = name
    if body.description is not None:
        role.description = body.description.strip() or None
    add_audit_log(db, current_user, "update", "role", 0, role.name,
                  details=f"Renombrado de «{old}»" if old != role.name else "Descripción actualizada")
    await db.commit()
    return RoleOut(key=role.key, name=role.name, description=role.description)


@router.delete("/roles/{key}", status_code=204)
async def delete_role(key: str, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete, func
    from app.models.user import User

    role = await _get_role(db, key)
    in_use = (await db.execute(select(func.count()).select_from(User).where(User.role == key))).scalar()
    if in_use:
        raise HTTPException(409, f"Hay {in_use} usuario(s) con este rol: asignales otro antes de borrarlo")
    await db.execute(delete(RolePermission).where(RolePermission.role == key))
    await db.delete(role)
    add_audit_log(db, current_user, "delete", "role", 0, role.name)
    await db.commit()


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
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    role_row = await _get_role(db, role)
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
    add_audit_log(db, current_user, "permission", "role", 0, role_row.name,
                  details=f"{section}: ver={'sí' if body.can_view else 'no'}, editar={'sí' if body.can_edit else 'no'}")
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
    current_user=Depends(require_admin),
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
    add_audit_log(db, current_user, "permission", "user", user_id, f"usuario #{user_id}",
                  details=f"{section}: ver={'sí' if body.can_view else 'no'}, editar={'sí' if body.can_edit else 'no'}")
    await db.commit()
    return UserPermissionOut(section=section, can_view=perm.can_view, can_edit=perm.can_edit, is_override=True)


@router.delete("/users/{user_id}/{section}", status_code=204)
async def delete_user_permission(
    user_id: int,
    section: str,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id, UserPermission.section == section)
    )
    perm = result.scalar_one_or_none()
    if perm:
        await db.delete(perm)
        add_audit_log(db, current_user, "permission", "user", user_id, f"usuario #{user_id}",
                      details=f"{section}: vuelve al permiso del rol")
        await db.commit()
