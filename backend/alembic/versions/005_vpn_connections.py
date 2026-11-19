"""vpn connections table

Revision ID: 005
Revises: 004
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vpn_connections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("vpn_type", sa.String(20), nullable=False),
        sa.Column("router_id", sa.Integer, sa.ForeignKey("mikrotik_routers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("router_name", sa.String(100), nullable=True),
        sa.Column("wg_server_endpoint", sa.String(255), nullable=True),
        sa.Column("wg_server_port", sa.Integer, nullable=True, server_default="51820"),
        sa.Column("wg_server_public_key", sa.String(100), nullable=True),
        sa.Column("wg_client_private_key", sa.String(100), nullable=True),
        sa.Column("wg_client_public_key", sa.String(100), nullable=True),
        sa.Column("wg_client_ip", sa.String(50), nullable=True),
        sa.Column("wg_server_wg_ip", sa.String(50), nullable=True),
        sa.Column("wg_keepalive", sa.Integer, nullable=True, server_default="25"),
        sa.Column("l2tp_server_host", sa.String(255), nullable=True),
        sa.Column("l2tp_username", sa.String(100), nullable=True),
        sa.Column("l2tp_password", sa.String(100), nullable=True),
        sa.Column("l2tp_ipsec_secret", sa.String(100), nullable=True),
        sa.Column("l2tp_local_ip", sa.String(50), nullable=True),
        sa.Column("l2tp_remote_ip", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table("vpn_connections")
