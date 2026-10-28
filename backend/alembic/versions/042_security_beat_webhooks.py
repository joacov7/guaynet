"""security: captured BEAT webhook notifications

Revision ID: 042
Revises: 041
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_beat_webhooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("remote_ip", sa.String(45), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=True),
        sa.Column("event_detail", sa.JSON(), nullable=True),
        sa.Column("fetch_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("fetch_error", sa.Text(), nullable=True),
    )
    op.create_index("ix_sec_beat_webhooks_received_at", "sec_beat_webhooks", ["received_at"])
    op.create_index("ix_sec_beat_webhooks_event_id", "sec_beat_webhooks", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_sec_beat_webhooks_event_id", "sec_beat_webhooks")
    op.drop_index("ix_sec_beat_webhooks_received_at", "sec_beat_webhooks")
    op.drop_table("sec_beat_webhooks")
