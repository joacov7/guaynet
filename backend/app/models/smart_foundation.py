"""Initial Smart domain models.

These models intentionally reuse the existing User identity while keeping
Smart organizations, installations and authorization separate from ISP and
security-domain tables.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin


def _uuid_pk():
    return mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class SmartOrganization(Base, TimestampMixin):
    __tablename__ = "smart_organizations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    tax_id: Mapped[str | None] = mapped_column(String(30))
    organization_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="family")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    __table_args__ = (
        CheckConstraint("organization_type IN ('family','business','industrial','other')", name="ck_smart_org_type"),
        CheckConstraint("status IN ('active','suspended','archived')", name="ck_smart_org_status"),
    )


class SmartInstallation(Base, TimestampMixin):
    __tablename__ = "smart_installations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("smart_organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    installation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    province: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2), nullable=False, server_default="AR")
    timezone: Mapped[str] = mapped_column(String(60), nullable=False, server_default="America/Argentina/Buenos_Aires")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    __table_args__ = (
        CheckConstraint("installation_type IN ('home','commercial','industrial','other')", name="ck_smart_installation_type"),
        CheckConstraint("status IN ('active','suspended','maintenance','archived')", name="ck_smart_installation_status"),
        UniqueConstraint("id", "organization_id", name="uq_smart_installation_id_org"),
        Index("ix_smart_installations_org_status", "organization_id", "status"),
    )


class SmartRole(Base, TimestampMixin):
    __tablename__ = "smart_roles"
    id: Mapped[uuid.UUID] = _uuid_pk()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("smart_organizations.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(250))
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        CheckConstraint("scope IN ('organization','installation')", name="ck_smart_role_scope"),
        CheckConstraint("(is_system = true AND organization_id IS NULL) OR (is_system = false AND organization_id IS NOT NULL)", name="ck_smart_role_owner"),
        Index("uq_smart_system_role_scope_key", "scope", "key", unique=True, postgresql_where=text("organization_id IS NULL")),
        Index("uq_smart_custom_role_scope_key_org", "scope", "key", "organization_id", unique=True, postgresql_where=text("organization_id IS NOT NULL")),
    )


class SmartPermission(Base):
    __tablename__ = "smart_permissions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    module: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default="normal")
    __table_args__ = (
        CheckConstraint("risk_level IN ('low','normal','sensitive','critical')", name="ck_smart_permission_risk"),
    )


class SmartRolePermission(Base):
    __tablename__ = "smart_role_permissions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_permissions.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_smart_role_permission"),)


class SmartOrganizationMember(Base, TimestampMixin):
    __tablename__ = "smart_organization_members"
    id: Mapped[uuid.UUID] = _uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_roles.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_smart_org_member_user"),
        CheckConstraint("status IN ('invited','active','suspended','revoked')", name="ck_smart_org_member_status"),
        Index("ix_smart_org_members_user_status", "user_id", "status"),
    )


class SmartInstallationMember(Base, TimestampMixin):
    __tablename__ = "smart_installation_members"
    id: Mapped[uuid.UUID] = _uuid_pk()
    installation_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_installations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_roles.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schedule: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    __table_args__ = (
        UniqueConstraint("installation_id", "user_id", name="uq_smart_install_member_user"),
        CheckConstraint("status IN ('active','suspended','revoked')", name="ck_smart_install_member_status"),
        CheckConstraint("ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at", name="ck_smart_install_member_dates"),
        Index("ix_smart_install_members_user_status", "user_id", "status"),
    )


class SmartMemberPermission(Base):
    __tablename__ = "smart_member_permissions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    installation_member_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_installation_members.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_permissions.id", ondelete="CASCADE"), nullable=False)
    effect: Mapped[str] = mapped_column(String(10), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint("effect IN ('grant','deny')", name="ck_smart_member_permission_effect"),
        UniqueConstraint("installation_member_id", "permission_id", name="uq_smart_member_permission"),
    )


class SmartInvitation(Base):
    __tablename__ = "smart_invitations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_organizations.id", ondelete="CASCADE"))
    installation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_installations.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_roles.id", ondelete="RESTRICT"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    accepted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint("(organization_id IS NOT NULL AND installation_id IS NULL) OR (organization_id IS NULL AND installation_id IS NOT NULL)", name="ck_smart_invitation_single_scope"),
        CheckConstraint("status IN ('pending','accepted','expired','revoked')", name="ck_smart_invitation_status"),
        Index("ix_smart_invitations_email_status", "email", "status"),
    )


class SmartAuditEvent(Base):
    __tablename__ = "smart_audit_events"
    id: Mapped[uuid.UUID] = _uuid_pk()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_organizations.id", ondelete="SET NULL"))
    installation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("smart_installations.id", ondelete="SET NULL"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100))
    result: Mapped[str] = mapped_column(String(20), nullable=False, server_default="success")
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="api")
    request_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint("actor_type IN ('user','gateway','system','ai')", name="ck_smart_audit_actor_type"),
        CheckConstraint("result IN ('success','denied','failed')", name="ck_smart_audit_result"),
        Index("ix_smart_audit_installation_created", "installation_id", "created_at"),
        Index("ix_smart_audit_user_created", "user_id", "created_at"),
    )


class SmartGateway(Base, TimestampMixin):
    """One outbound-connected automation gateway per Smart installation."""
    __tablename__ = "smart_gateways"
    id: Mapped[uuid.UUID] = _uuid_pk()
    installation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("smart_installations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    gateway_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="home_assistant")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    external_gateway_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    credential_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    credential_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    software_version: Mapped[str | None] = mapped_column(String(80))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    __table_args__ = (
        CheckConstraint("gateway_type IN ('home_assistant')", name="ck_smart_gateway_type"),
        CheckConstraint("status IN ('pending','online','offline','maintenance','revoked')", name="ck_smart_gateway_status"),
    )


class SmartDevice(Base, TimestampMixin):
    """A physical/logical device discovered through a gateway."""
    __tablename__ = "smart_devices"
    id: Mapped[uuid.UUID] = _uuid_pk()
    gateway_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("smart_gateways.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_device_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    software_version: Mapped[str | None] = mapped_column(String(80))
    area_name: Mapped[str | None] = mapped_column(String(120))
    device_class: Mapped[str | None] = mapped_column(String(80))
    availability: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unknown")
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("gateway_id", "external_device_id", name="uq_smart_device_gateway_external"),
        CheckConstraint("availability IN ('available','unavailable','unknown')", name="ck_smart_device_availability"),
        Index("ix_smart_devices_gateway_availability", "gateway_id", "availability"),
    )


class SmartEntity(Base, TimestampMixin):
    """A controllable or observable entity exposed by a gateway."""
    __tablename__ = "smart_entities"
    id: Mapped[uuid.UUID] = _uuid_pk()
    gateway_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("smart_gateways.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("smart_devices.id", ondelete="SET NULL"),
    )
    external_entity_id: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str | None] = mapped_column(String(500))
    availability: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unknown")
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("gateway_id", "external_entity_id", name="uq_smart_entity_gateway_external"),
        CheckConstraint("availability IN ('available','unavailable','unknown')", name="ck_smart_entity_availability"),
        Index("ix_smart_entities_gateway_domain", "gateway_id", "domain"),
        Index("ix_smart_entities_device", "device_id"),
    )
