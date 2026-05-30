from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


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


def require_permission(section: str, action: str = "view"):
    async def _dep(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        if current_user.role == "admin" or current_user.is_superuser:
            return current_user
        from app.models.permission import RolePermission
        from sqlalchemy import select as sa_select
        result = await db.execute(
            sa_select(RolePermission).where(
                RolePermission.role == current_user.role,
                RolePermission.section == section,
            )
        )
        perm = result.scalar_one_or_none()
        if not perm:
            raise HTTPException(status_code=403, detail="Sin permiso")
        if action == "view" and not perm.can_view:
            raise HTTPException(status_code=403, detail="Sin permiso de lectura")
        if action == "edit" and not perm.can_edit:
            raise HTTPException(status_code=403, detail="Sin permiso de edición")
        return current_user
    return _dep
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
