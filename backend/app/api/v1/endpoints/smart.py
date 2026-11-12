"""Smart organization and installation bootstrap API.

This first vertical slice deliberately excludes invitations, custom roles and
Home Assistant connectivity. Every write is transactional and audited.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.smart_foundation import (
    SmartAuditEvent,
    SmartInstallation,
    SmartInstallationMember,
    SmartOrganization,
    SmartOrganizationMember,
    SmartRole,
)

router = APIRouter()


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    organization_type: str = Field(default="family", pattern="^(family|business|industrial|other)$")
    legal_name: str | None = Field(default=None, max_length=200)
    tax_id: str | None = Field(default=None, max_length=30)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    organization_type: str
    status: str


class InstallationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    installation_type: str = Field(pattern="^(home|commercial|industrial|other)$")
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)


class InstallationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    installation_type: str
    status: str


async def _system_role(db: AsyncSession, key: str, scope: str) -> SmartRole:
    result = await db.execute(
        select(SmartRole).where(
            SmartRole.key == key,
            SmartRole.scope == scope,
            SmartRole.is_system.is_(True),
            SmartRole.organization_id.is_(None),
        )
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=503, detail="Roles Smart no inicializados")
    return role


@router.post("/organizations", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    owner_role = await _system_role(db, "org_owner", "organization")
    organization = SmartOrganization(
        name=body.name.strip(),
        organization_type=body.organization_type,
        legal_name=body.legal_name,
        tax_id=body.tax_id,
    )
    db.add(organization)
    await db.flush()

    db.add(SmartOrganizationMember(
        organization_id=organization.id,
        user_id=current_user.id,
        role_id=owner_role.id,
        status="active",
    ))
    db.add(SmartAuditEvent(
        organization_id=organization.id,
        user_id=current_user.id,
        actor_type="user",
        action="organization.created",
        resource_type="organization",
        resource_id=str(organization.id),
        result="success",
        source="api",
    ))
    await db.commit()
    await db.refresh(organization)
    return organization


@router.get("/organizations", response_model=list[OrganizationRead])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(SmartOrganization)
        .join(SmartOrganizationMember, SmartOrganizationMember.organization_id == SmartOrganization.id)
        .where(
            SmartOrganizationMember.user_id == current_user.id,
            SmartOrganizationMember.status == "active",
            SmartOrganization.status == "active",
        )
        .order_by(SmartOrganization.name)
    )
    return result.scalars().all()


@router.post(
    "/organizations/{organization_id}/installations",
    response_model=InstallationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_installation(
    organization_id: UUID,
    body: InstallationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    organization_result = await db.execute(
        select(SmartOrganization)
        .join(SmartOrganizationMember, SmartOrganizationMember.organization_id == SmartOrganization.id)
        .join(SmartRole, SmartRole.id == SmartOrganizationMember.role_id)
        .where(
            SmartOrganization.id == organization_id,
            SmartOrganization.status == "active",
            SmartOrganizationMember.user_id == current_user.id,
            SmartOrganizationMember.status == "active",
            SmartRole.scope == "organization",
            SmartRole.key.in_(("org_owner", "org_admin")),
            SmartRole.organization_id.is_(None),
        )
    )
    organization = organization_result.scalar_one_or_none()
    if organization is None:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    installation_role = await _system_role(db, "installation_admin", "installation")
    installation = SmartInstallation(
        organization_id=organization.id,
        name=body.name.strip(),
        installation_type=body.installation_type,
        address=body.address,
        city=body.city,
        province=body.province,
    )
    db.add(installation)
    await db.flush()

    db.add(SmartInstallationMember(
        installation_id=installation.id,
        user_id=current_user.id,
        role_id=installation_role.id,
        status="active",
    ))
    db.add(SmartAuditEvent(
        organization_id=organization.id,
        installation_id=installation.id,
        user_id=current_user.id,
        actor_type="user",
        action="installation.created",
        resource_type="installation",
        resource_id=str(installation.id),
        result="success",
        source="api",
    ))
    await db.commit()
    await db.refresh(installation)
    return installation
