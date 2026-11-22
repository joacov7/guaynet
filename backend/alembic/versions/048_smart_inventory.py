"""Add Smart gateway, device and entity inventory.

Revision ID: 048
Revises: 047
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "smart_gateways",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_installations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("gateway_type", sa.String(40), nullable=False, server_default="home_assistant"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("external_gateway_id", sa.String(160), unique=True),
        sa.Column("software_version", sa.String(80)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("gateway_type IN ('home_assistant')", name="ck_smart_gateway_type"),
        sa.CheckConstraint("status IN ('pending','online','offline','maintenance','revoked')", name="ck_smart_gateway_status"),
    )

    op.create_table(
        "smart_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("gateway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_gateways.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_device_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("manufacturer", sa.String(120)),
        sa.Column("model", sa.String(120)),
        sa.Column("software_version", sa.String(80)),
        sa.Column("area_name", sa.String(120)),
        sa.Column("device_class", sa.String(80)),
        sa.Column("availability", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("gateway_id", "external_device_id", name="uq_smart_device_gateway_external"),
        sa.CheckConstraint("availability IN ('available','unavailable','unknown')", name="ck_smart_device_availability"),
    )
    op.create_index("ix_smart_devices_gateway_availability", "smart_devices", ["gateway_id", "availability"])

    op.create_table(
        "smart_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("gateway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_gateways.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("smart_devices.id", ondelete="SET NULL")),
        sa.Column("external_entity_id", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(80)),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("state", sa.String(500)),
        sa.Column("availability", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_changed_at", sa.DateTime(timezone=True)),
        sa.Column("last_reported_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("gateway_id", "external_entity_id", name="uq_smart_entity_gateway_external"),
        sa.CheckConstraint("availability IN ('available','unavailable','unknown')", name="ck_smart_entity_availability"),
    )
    op.create_index("ix_smart_entities_gateway_domain", "smart_entities", ["gateway_id", "domain"])
    op.create_index("ix_smart_entities_device", "smart_entities", ["device_id"])


def downgrade() -> None:
    op.drop_table("smart_entities")
    op.drop_table("smart_devices")
    op.drop_table("smart_gateways")
