"""Smart organization and installation bootstrap API.

This first vertical slice deliberately excludes invitations, custom roles and
Home Assistant connectivity. Every write is transactional and audited.
"""
from datetime import datetime, timezone
import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.smart_permissions import require_smart_permission
from app.core.smart_gateway_auth import get_authenticated_smart_gateway
from app.models.smart_foundation import (
    SmartAuditEvent,
    SmartInstallation,
    SmartInstallationMember,
    SmartOrganization,
    SmartOrganizationMember,
    SmartRole,
    SmartGateway,
    SmartDevice,
    SmartEntity,
)

router = APIRouter()


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    organization_type: str = Field(default="family", pattern="^(family|business|industrial|other)$")
    legal_name: str | None = Field(default=None, max_length=200)
    tax_id: str | None = Field(default=None, max_length=30)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return value


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

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return value


class InstallationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    installation_type: str
    status: str




class GatewayHeartbeat(BaseModel):
    external_gateway_id: str = Field(min_length=8, max_length=160)
    software_version: str | None = Field(default=None, max_length=80)
    capabilities: dict = Field(default_factory=dict)


class GatewayHeartbeatRead(BaseModel):
    gateway_id: UUID
    installation_id: UUID
    status: str
    accepted_at: datetime


class GatewayCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    gateway_type: str = Field(default="home_assistant", pattern="^home_assistant$")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return value


class GatewayCredentialCreated(BaseModel):
    id: UUID
    installation_id: UUID
    name: str
    gateway_type: str
    status: str
    credential: str
    credential_rotated_at: datetime


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    external_device_id: str
    name: str
    manufacturer: str | None
    model: str | None
    area_name: str | None
    device_class: str | None
    availability: str
    attributes: dict


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    device_id: UUID | None
    external_entity_id: str
    domain: str
    entity_type: str | None
    name: str
    state: str | None
    availability: str
    attributes: dict


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




@router.post(
    "/gateway/heartbeat",
    response_model=GatewayHeartbeatRead,
)
async def smart_gateway_heartbeat(
    body: GatewayHeartbeat,
    gateway: SmartGateway = Depends(get_authenticated_smart_gateway),
    db: AsyncSession = Depends(get_db),
):
    if gateway.external_gateway_id and gateway.external_gateway_id != body.external_gateway_id:
        raise HTTPException(status_code=409, detail="El identificador del gateway no coincide")
    if gateway.status == "revoked":
        raise HTTPException(status_code=401, detail="Gateway revocado")

    now = datetime.now(timezone.utc)
    gateway.external_gateway_id = body.external_gateway_id
    gateway.software_version = body.software_version
    gateway.capabilities = body.capabilities
    gateway.status = "online"
    gateway.last_seen_at = now
    await db.commit()
    return GatewayHeartbeatRead(
        gateway_id=gateway.id,
        installation_id=gateway.installation_id,
        status=gateway.status,
        accepted_at=now,
    )


@router.post(
    "/installations/{installation_id}/gateways",
    response_model=GatewayCredentialCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_smart_permission("installation.settings.manage"))],
)
async def create_installation_gateway(
    installation_id: UUID,
    body: GatewayCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    existing = await db.execute(
        select(SmartGateway.id).where(SmartGateway.installation_id == installation_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Esta instalación ya tiene un gateway")
    credential = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    gateway = SmartGateway(
        installation_id=installation_id,
        gateway_type=body.gateway_type,
        name=body.name,
        status="pending",
        credential_hash=hashlib.sha256(credential.encode("utf-8")).hexdigest(),
        credential_rotated_at=now,
    )
    db.add(gateway)
    await db.flush()
    db.add(SmartAuditEvent(
        installation_id=installation_id,
        actor_type="user",
        user_id=current_user.id,
        action="gateway.credential.created",
        resource_type="gateway",
        resource_id=str(gateway.id),
        result="success",
        source="api",
    ))
    await db.commit()
    await db.refresh(gateway)
    return GatewayCredentialCreated(
        id=gateway.id,
        installation_id=gateway.installation_id,
        name=gateway.name,
        gateway_type=gateway.gateway_type,
        status=gateway.status,
        credential=credential,
        credential_rotated_at=gateway.credential_rotated_at,
    )


@router.get(
    "/installations/{installation_id}/devices",
    response_model=list[DeviceRead],
    dependencies=[Depends(require_smart_permission("devices.read"))],
)
async def list_installation_devices(
    installation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SmartDevice)
        .join(SmartGateway, SmartGateway.id == SmartDevice.gateway_id)
        .where(
            SmartGateway.installation_id == installation_id,
            SmartGateway.status != "revoked",
        )
        .order_by(SmartDevice.name)
    )
    return result.scalars().all()


@router.get(
    "/installations/{installation_id}/entities",
    response_model=list[EntityRead],
    dependencies=[Depends(require_smart_permission("devices.read"))],
)
async def list_installation_entities(
    installation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SmartEntity)
        .join(SmartGateway, SmartGateway.id == SmartEntity.gateway_id)
        .where(
            SmartGateway.installation_id == installation_id,
            SmartGateway.status != "revoked",
        )
        .order_by(SmartEntity.name)
    )
    return result.scalars().all()


@router.post("/organizations", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    owner_role = await _system_role(db, "org_owner", "organization")
    organization = SmartOrganization(
        name=body.name,
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


@router.get("/installations", response_model=list[InstallationRead])
async def list_installations(
    organization_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List only installations where the caller has an active direct membership."""
    now = datetime.now(timezone.utc)
    query = (
        select(SmartInstallation)
        .join(
            SmartInstallationMember,
            SmartInstallationMember.installation_id == SmartInstallation.id,
        )
        .join(SmartRole, SmartRole.id == SmartInstallationMember.role_id)
        .where(
            SmartInstallationMember.user_id == current_user.id,
            SmartInstallationMember.status == "active",
            or_(SmartInstallationMember.starts_at.is_(None), SmartInstallationMember.starts_at <= now),
            or_(SmartInstallationMember.ends_at.is_(None), SmartInstallationMember.ends_at > now),
            SmartInstallationMember.schedule == {},
            SmartRole.scope == "installation",
            or_(
                SmartRole.organization_id.is_(None),
                SmartRole.organization_id == SmartInstallation.organization_id,
            ),
            SmartInstallation.status == "active",
        )
    )
    if organization_id is not None:
        query = query.where(SmartInstallation.organization_id == organization_id)
    result = await db.execute(query.order_by(SmartInstallation.name))
    return result.scalars().all()


@router.get("/installations/{installation_id}", response_model=InstallationRead)
async def get_installation(
    installation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return an installation only to users with active direct membership."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(SmartInstallation)
        .join(
            SmartInstallationMember,
            SmartInstallationMember.installation_id == SmartInstallation.id,
        )
        .join(SmartRole, SmartRole.id == SmartInstallationMember.role_id)
        .where(
            SmartInstallation.id == installation_id,
            SmartInstallationMember.user_id == current_user.id,
            SmartInstallationMember.status == "active",
            or_(SmartInstallationMember.starts_at.is_(None), SmartInstallationMember.starts_at <= now),
            or_(SmartInstallationMember.ends_at.is_(None), SmartInstallationMember.ends_at > now),
            SmartInstallationMember.schedule == {},
            SmartRole.scope == "installation",
            or_(
                SmartRole.organization_id.is_(None),
                SmartRole.organization_id == SmartInstallation.organization_id,
            ),
            SmartInstallation.status == "active",
        )
    )
    installation = result.scalar_one_or_none()
    if installation is None:
        # Same response for missing and unauthorized resources to avoid enumeration.
        raise HTTPException(status_code=404, detail="Instalación no encontrada")
    return installation


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
