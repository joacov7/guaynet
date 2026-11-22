"""Add network controllers and EdgeMAX device classification.

Revision ID: 046
Revises: 045
"""
from alembic import op
import sqlalchemy as sa

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL enum values are additive; IF NOT EXISTS keeps this safe on retries.
    op.execute("ALTER TYPE ubiquitidevicetype ADD VALUE IF NOT EXISTS 'edgemax_switch'")

    controller_type = sa.Enum("unifi_network", name="networkcontrollertype")
    controller_status = sa.Enum(
        "unknown", "online", "offline", "error",
        name="networkcontrollerstatus",
    )
    op.create_table(
        "network_controllers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("controller_type", controller_type, nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("site_name", sa.String(length=100), nullable=True),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("credentials_encrypted", sa.String(length=1200), nullable=True),
        sa.Column("verify_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", controller_status, nullable=False, server_default="unknown"),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "ubiquiti_devices",
        sa.Column("controller_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_ubiquiti_devices_controller_id", "ubiquiti_devices", ["controller_id"])
    op.create_foreign_key(
        "fk_ubiquiti_devices_controller_id_network_controllers",
        "ubiquiti_devices",
        "network_controllers",
        ["controller_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ubiquiti_devices_controller_id_network_controllers",
        "ubiquiti_devices",
        type_="foreignkey",
    )
    op.drop_index("ix_ubiquiti_devices_controller_id", table_name="ubiquiti_devices")
    op.drop_column("ubiquiti_devices", "controller_id")
    op.drop_table("network_controllers")
    op.execute("DROP TYPE IF EXISTS networkcontrollerstatus")
    op.execute("DROP TYPE IF EXISTS networkcontrollertype")
    # PostgreSQL enum values cannot be removed safely; edgemax_switch remains unused.
