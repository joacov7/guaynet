"""Track historical CPE identities for ISP clients.

Revision ID: 045
Revises: 044
"""
from alembic import op
import sqlalchemy as sa

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_device_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("mikrotik_routers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mac_address", sa.String(length=17), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_reason", sa.String(length=30), nullable=False, server_default="initial"),
    )
    op.create_index("ix_client_device_history_client_id", "client_device_history", ["client_id"])
    op.create_index("ix_client_device_history_router_id", "client_device_history", ["router_id"])
    op.create_index("ix_client_device_history_mac_address", "client_device_history", ["mac_address"])

    # Seed current CPE assignments so the first replacement does not lose the old MAC.
    op.execute("""
        INSERT INTO client_device_history (client_id, router_id, mac_address, ip_address, change_reason)
        SELECT id, router_id, mac_address, ip_address, 'initial'
        FROM clients
        WHERE mac_address IS NOT NULL AND trim(mac_address) <> ''
    """)


def downgrade() -> None:
    op.drop_index("ix_client_device_history_mac_address", table_name="client_device_history")
    op.drop_index("ix_client_device_history_router_id", table_name="client_device_history")
    op.drop_index("ix_client_device_history_client_id", table_name="client_device_history")
    op.drop_table("client_device_history")
