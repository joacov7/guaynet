"""Add audit logs, bandwidth samples, user roles, geo coords

Revision ID: 003
Revises: 002
Create Date: 2026-05-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("username", sa.String(50), nullable=False, server_default="system"),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("entity_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    op.create_table(
        "bandwidth_samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("mikrotik_routers.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=False),
        sa.Column("queue_name", sa.String(200), nullable=False),
        sa.Column("upload_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("download_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bw_router_time", "bandwidth_samples", ["router_id", "sampled_at"])

    op.add_column("users", sa.Column("role", sa.String(20), nullable=False, server_default="operator"))

    for table in ("mikrotik_routers", "ubiquiti_devices", "clients"):
        op.add_column(table, sa.Column("latitude", sa.Float(), nullable=True))
        op.add_column(table, sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    for table in ("clients", "ubiquiti_devices", "mikrotik_routers"):
        op.drop_column(table, "longitude")
        op.drop_column(table, "latitude")
    op.drop_column("users", "role")
    op.drop_index("ix_bw_router_time", table_name="bandwidth_samples")
    op.drop_table("bandwidth_samples")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_table("audit_logs")
