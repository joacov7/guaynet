"""wan management tables

Revision ID: 022
Revises: 021
Create Date: 2026-10-18
"""
from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wan_interfaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("mikrotik_routers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interface_name", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=True),
        sa.Column("weight", sa.Integer(), default=1),
        sa.Column("cap_gb", sa.Integer(), nullable=True),
        sa.Column("manual_override", sa.Boolean(), default=False),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("accumulated_rx_bytes", sa.BigInteger(), default=0),
        sa.Column("accumulated_tx_bytes", sa.BigInteger(), default=0),
        sa.Column("last_rx_bytes", sa.BigInteger(), nullable=True),
        sa.Column("last_tx_bytes", sa.BigInteger(), nullable=True),
    )
    op.create_table(
        "wan_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wan_interface_id", sa.Integer(), sa.ForeignKey("wan_interfaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("days", sa.String(64), nullable=False, server_default="mon,tue,wed,thu,fri,sat,sun"),
        sa.Column("time_start", sa.String(8), nullable=False),
        sa.Column("time_end", sa.String(8), nullable=False),
    )


def downgrade():
    op.drop_table("wan_schedules")
    op.drop_table("wan_interfaces")
