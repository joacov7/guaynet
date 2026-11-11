"""Installation-scoped authorization for the Smart platform.

Organization membership deliberately does not imply access to every installation.
Critical permissions are not granted through this generic dependency.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.smart_foundation import (
    SmartInstallation,
    SmartInstallationMember,
    SmartOrganization,
    SmartMemberPermission,
    SmartPermission,
    SmartRole,
    SmartRolePermission,
)


def _permission_is_allowed(role_granted: bool, override_effect: str | None, risk_level: str) -> bool:
    """Pure policy decision; critical operations are handled by a separate flow."""
    if risk_level == "critical":
        return False
    if override_effect == "deny":
        return False
    if override_effect == "grant":
        return True
    return role_granted


def require_smart_permission(permission_code: str):
    """Require an active, direct membership in the installation in the URL.

    The endpoint must expose an `installation_id` path parameter. Access is
    default-deny; a deny override wins over both role grants and explicit grants.
    Non-empty schedules fail closed until schedule evaluation is implemented.
    """
    async def _dependency(
        request: Request,
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        raw_installation_id = request.path_params.get("installation_id")
        try:
            installation_id = UUID(str(raw_installation_id))
        except (TypeError, ValueError):
            raise HTTPException(status_code=404, detail="Instalación no encontrada")

        now = datetime.now(timezone.utc)
        installation_result = await db.execute(
            select(SmartInstallation, SmartOrganization)
            .join(SmartOrganization, SmartOrganization.id == SmartInstallation.organization_id)
            .where(
                SmartInstallation.id == installation_id,
                SmartInstallation.status == "active",
                SmartOrganization.status == "active",
            )
        )
        installation_row = installation_result.one_or_none()
        if installation_row is None:
            raise HTTPException(status_code=404, detail="Instalación no encontrada")

        membership_result = await db.execute(
            select(SmartInstallationMember, SmartRole)
            .join(SmartRole, SmartRole.id == SmartInstallationMember.role_id)
            .where(
                SmartInstallationMember.installation_id == installation_id,
                SmartInstallationMember.user_id == current_user.id,
                SmartInstallationMember.status == "active",
                SmartRole.scope == "installation",
                or_(SmartInstallationMember.starts_at.is_(None), SmartInstallationMember.starts_at <= now),
                or_(SmartInstallationMember.ends_at.is_(None), SmartInstallationMember.ends_at > now),
            )
        )
        membership_row = membership_result.one_or_none()
        if membership_row is None:
            raise HTTPException(status_code=403, detail="No tenés acceso a esta instalación")

        member, role = membership_row
        if member.schedule:
            raise HTTPException(status_code=403, detail="El acceso horario todavía no está habilitado para esta instalación")

        permission_result = await db.execute(
            select(SmartPermission).where(SmartPermission.code == permission_code)
        )
        permission = permission_result.scalar_one_or_none()
        if permission is None:
            raise HTTPException(status_code=403, detail="Permiso no configurado")

        role_grant_result = await db.execute(
            select(SmartRolePermission.id)
            .join(SmartPermission, SmartPermission.id == SmartRolePermission.permission_id)
            .where(
                SmartRolePermission.role_id == role.id,
                SmartPermission.code == permission_code,
            )
        )
        role_granted = role_grant_result.scalar_one_or_none() is not None

        override_result = await db.execute(
            select(SmartMemberPermission).where(
                SmartMemberPermission.installation_member_id == member.id,
                SmartMemberPermission.permission_id == permission.id,
                or_(SmartMemberPermission.expires_at.is_(None), SmartMemberPermission.expires_at > now),
            )
        )
        override = override_result.scalar_one_or_none()
        allowed = _permission_is_allowed(
            role_granted=role_granted,
            override_effect=override.effect if override else None,
            risk_level=permission.risk_level,
        )
        if not allowed:
            detail = (
                "Esta operación requiere autorización reforzada"
                if permission.risk_level == "critical"
                else "No tenés permiso para esta operación"
            )
            raise HTTPException(status_code=403, detail=detail)

        request.state.smart_installation_id = installation_id
        request.state.smart_membership_id = member.id
        request.state.smart_permission = permission_code
        return current_user

    return _dependency
