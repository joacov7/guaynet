from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_token(token)
    if user_id is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_superuser(current_user=Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Acceso denegado: se requieren permisos de administrador")
    return current_user


async def require_admin(current_user=Depends(get_current_user)):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Se requieren permisos de administrador")
    return current_user


def _is_admin(user) -> bool:
    return user.role == "admin" or bool(user.is_superuser)


async def effective_permissions(db: AsyncSession, user) -> dict:
    """{section: (can_view, can_edit)} for a non-admin: role baseline, user overrides win."""
    from app.models.permission import RolePermission
    from app.models.user_permission import UserPermission

    perms = {
        r.section: (r.can_view, r.can_edit)
        for r in (await db.execute(select(RolePermission).where(RolePermission.role == user.role))).scalars()
    }
    for r in (await db.execute(select(UserPermission).where(UserPermission.user_id == user.id))).scalars():
        perms[r.section] = (r.can_view, r.can_edit)
    return perms


def require_permission(section: str, action: str = "view"):
    """Endpoint-level check of one section and action ("view" or "edit")."""
    async def _dep(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        if _is_admin(current_user):
            return current_user
        view, edit = (await effective_permissions(db, current_user)).get(section, (False, False))
        if not (edit if action == "edit" else view):
            raise HTTPException(
                status_code=403,
                detail="Sin permiso de edición" if action == "edit" else "Sin permiso de lectura",
            )
        return current_user
    return _dep


_READ_METHODS = {"GET", "HEAD", "OPTIONS"}


def section_guard(section: str, also_view: tuple = ()):
    """
    Router-level permission check (Usuarios → Permisos), applied with
    include_router(..., dependencies=[Depends(section_guard(...))]):
      - GET/HEAD: can_view on `section` or on any of `also_view` (other screens
        that read this data, e.g. the client form lists plans and routers).
      - any other method: can_edit on `section`.
    Admins always pass. Endpoint-level checks (e.g. require_admin) still apply.
    """
    async def _dep(request: Request, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        if _is_admin(current_user):
            return current_user
        perms = await effective_permissions(db, current_user)
        if request.method in _READ_METHODS:
            if not any(perms.get(s, (False, False))[0] for s in (section, *also_view)):
                raise HTTPException(status_code=403, detail="No tenés permiso para ver esta sección")
        elif not perms.get(section, (False, False))[1]:
            raise HTTPException(status_code=403, detail="No tenés permiso para modificar esta sección")
        return current_user
    return _dep


def add_audit_log(
    db: AsyncSession,
    user,
    action: str,
    entity_type: str,
    entity_id: int,
    entity_name: str,
    details: Optional[str] = None,
) -> None:
    from app.models.audit import AuditLog
    db.add(AuditLog(
        user_id=user.id,
        username=user.username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        details=details,
    ))
