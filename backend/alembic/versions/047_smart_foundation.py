"""Create Smart organization, installation and authorization foundation.

Revision ID: 047
Revises: 046
"""
from uuid import UUID, uuid5, NAMESPACE_URL

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None

def _id(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, "guaynet-smart:" + value)

def upgrade() -> None:
    op.create_table(
        "smart_organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("legal_name", sa.String(200)),
        sa.Column("tax_id", sa.String(30)),
        sa.Column("organization_type", sa.String(30), nullable=False, server_default="family"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("organization_type IN ('family','business','industrial','other')", name="ck_smart_org_type"),
        sa.CheckConstraint("status IN ('active','suspended','archived')", name="ck_smart_org_status"),
    )
    op.create_table(
        "smart_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("installation_type", sa.String(30), nullable=False),
        sa.Column("address", sa.String(300)),
        sa.Column("city", sa.String(100)),
        sa.Column("province", sa.String(100)),
        sa.Column("country", sa.String(2), nullable=False, server_default="AR"),
        sa.Column("timezone", sa.String(60), nullable=False, server_default="America/Argentina/Buenos_Aires"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("installation_type IN ('home','commercial','industrial','other')", name="ck_smart_installation_type"),
        sa.CheckConstraint("status IN ('active','suspended','maintenance','archived')", name="ck_smart_installation_status"),
        sa.UniqueConstraint("id", "organization_id", name="uq_smart_installation_id_org"),
    )
    op.create_index("ix_smart_installations_organization_id", "smart_installations", ["organization_id"])
    op.create_index("ix_smart_installations_org_status", "smart_installations", ["organization_id", "status"])

    op.create_table(
        "smart_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_organizations.id", ondelete="CASCADE")),
        sa.Column("key", sa.String(60), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(250)),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("scope IN ('organization','installation')", name="ck_smart_role_scope"),
        sa.CheckConstraint("(is_system = true AND organization_id IS NULL) OR (is_system = false AND organization_id IS NOT NULL)", name="ck_smart_role_owner"),
    )
    op.create_index("uq_smart_system_role_scope_key", "smart_roles", ["scope", "key"], unique=True, postgresql_where=sa.text("organization_id IS NULL"))
    op.create_index("uq_smart_custom_role_scope_key_org", "smart_roles", ["scope", "key", "organization_id"], unique=True, postgresql_where=sa.text("organization_id IS NOT NULL"))

    op.create_table(
        "smart_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("module", sa.String(40), nullable=False),
        sa.Column("description", sa.String(250), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="normal"),
        sa.CheckConstraint("risk_level IN ('low','normal','sensitive','critical')", name="ck_smart_permission_risk"),
    )
    op.create_table(
        "smart_role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_permissions.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_smart_role_permission"),
    )
    op.create_table(
        "smart_organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_smart_org_member_user"),
        sa.CheckConstraint("status IN ('invited','active','suspended','revoked')", name="ck_smart_org_member_status"),
    )
    op.create_index("ix_smart_org_members_user_status", "smart_organization_members", ["user_id", "status"])

    op.create_table(
        "smart_installation_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("schedule", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["installation_id"], ["smart_installations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("installation_id", "user_id", name="uq_smart_install_member_user"),
        sa.CheckConstraint("status IN ('active','suspended','revoked')", name="ck_smart_install_member_status"),
        sa.CheckConstraint("ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at", name="ck_smart_install_member_dates"),
    )
    op.create_index("ix_smart_install_members_user_status", "smart_installation_members", ["user_id", "status"])

    op.create_table(
        "smart_member_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("installation_member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_installation_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("effect", sa.String(10), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("effect IN ('grant','deny')", name="ck_smart_member_permission_effect"),
        sa.UniqueConstraint("installation_member_id", "permission_id", name="uq_smart_member_permission"),
    )

    op.create_table(
        "smart_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_organizations.id", ondelete="CASCADE")),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_installations.id", ondelete="CASCADE")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("accepted_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("(organization_id IS NOT NULL AND installation_id IS NULL) OR (organization_id IS NULL AND installation_id IS NOT NULL)", name="ck_smart_invitation_single_scope"),
        sa.CheckConstraint("status IN ('pending','accepted','expired','revoked')", name="ck_smart_invitation_status"),
    )
    op.create_index("ix_smart_invitations_email_status", "smart_invitations", ["email", "status"])

    roles = [
        ("organization", "org_owner", "Propietario", "Administra la organización"),
        ("organization", "org_admin", "Administrador", "Administra miembros e instalaciones"),
        ("organization", "org_member", "Miembro", "Acceso básico a la organización"),
        ("installation", "installation_admin", "Administrador de instalación", "Administra la instalación"),
        ("installation", "technician", "Técnico", "Configura y mantiene equipos"),
        ("installation", "operator", "Operador", "Opera funciones autorizadas"),
        ("installation", "viewer", "Consulta", "Solo lectura"),
    ]
    permissions = [
        ("organization.read", "organization", "Ver organización", "low"),
        ("organization.members.manage", "organization", "Administrar miembros", "sensitive"),
        ("organization.installations.manage", "organization", "Administrar instalaciones", "sensitive"),
        ("installation.read", "core", "Ver instalación", "low"),
        ("installation.settings.manage", "core", "Modificar configuración", "sensitive"),
        ("installation.members.manage", "core", "Administrar accesos", "sensitive"),
        ("devices.read", "devices", "Ver dispositivos", "low"),
        ("devices.control", "devices", "Controlar dispositivos", "normal"),
        ("automations.manage", "automation", "Administrar automatizaciones", "sensitive"),
        ("energy.read", "energy", "Ver energía", "low"),
        ("security.read", "security", "Ver seguridad", "sensitive"),
        ("security.disarm", "security", "Desarmar alarma", "sensitive"),
        ("access.manage", "security", "Administrar accesos físicos", "critical"),
        ("audit.read", "core", "Ver auditoría", "sensitive"),
    ]
    role_ids = {key: _id("role:" + scope + ":" + key) for scope, key, *_ in roles}
    permission_ids = {code: _id("permission:" + code) for code, *_ in permissions}
    role_table = sa.table("smart_roles",
        sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("organization_id", postgresql.UUID(as_uuid=True)),
        sa.column("key", sa.String), sa.column("name", sa.String), sa.column("description", sa.String),
        sa.column("scope", sa.String), sa.column("is_system", sa.Boolean))
    op.bulk_insert(role_table, [
        {"id": role_ids[key], "organization_id": None, "key": key, "name": name, "description": desc, "scope": scope, "is_system": True}
        for scope, key, name, desc in roles
    ])
    permission_table = sa.table("smart_permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("code", sa.String),
        sa.column("module", sa.String), sa.column("description", sa.String), sa.column("risk_level", sa.String))
    op.bulk_insert(permission_table, [
        {"id": permission_ids[code], "code": code, "module": module, "description": desc, "risk_level": risk}
        for code, module, desc, risk in permissions
    ])
    role_map = {
        "org_owner": [p[0] for p in permissions if p[0].startswith("organization.")],
        "org_admin": ["organization.read", "organization.members.manage", "organization.installations.manage"],
        "org_member": ["organization.read"],
        "installation_admin": ["installation.read", "installation.settings.manage", "installation.members.manage", "devices.read", "devices.control", "automations.manage", "energy.read", "security.read", "security.disarm", "access.manage", "audit.read"],
        "technician": ["installation.read", "installation.settings.manage", "devices.read", "devices.control", "automations.manage", "energy.read", "security.read", "audit.read"],
        "operator": ["installation.read", "devices.read", "devices.control", "energy.read", "security.read"],
        "viewer": ["installation.read", "devices.read", "energy.read", "security.read"],
    }
    rp_table = sa.table("smart_role_permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("role_id", postgresql.UUID(as_uuid=True)),
        sa.column("permission_id", postgresql.UUID(as_uuid=True)))
    op.bulk_insert(rp_table, [
        {"id": _id("roleperm:" + role + ":" + code), "role_id": role_ids[role], "permission_id": permission_ids[code]}
        for role, codes in role_map.items() for code in codes
    ])


def downgrade() -> None:
    for table in (
        "smart_invitations", "smart_member_permissions", "smart_installation_members",
        "smart_organization_members", "smart_role_permissions", "smart_permissions",
        "smart_roles", "smart_installations", "smart_organizations",
    ):
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
