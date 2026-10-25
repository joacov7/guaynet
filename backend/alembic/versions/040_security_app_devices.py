"""security mobile app devices

Revision ID: 040
Revises: 039
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_app_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_name", sa.String(100), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False, server_default="android"),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("push_token", sa.String(512), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sec_app_devices_subscription_id", "sec_app_devices", ["subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_sec_app_devices_subscription_id", "sec_app_devices")
    op.drop_table("sec_app_devices")
