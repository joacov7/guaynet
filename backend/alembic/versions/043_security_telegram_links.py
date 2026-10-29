"""security: Telegram linking for titular and members

Revision ID: 043
Revises: 042
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sec_property_members", sa.Column("telegram_chat_id", sa.String(50), nullable=True))
    op.add_column("sec_property_members", sa.Column("telegram_linked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_sec_property_members_telegram_chat_id", "sec_property_members", ["telegram_chat_id"])

    op.create_table(
        "sec_telegram_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("sec_property_members.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_chat_id", sa.String(50), nullable=True),
    )
    op.create_index("ix_sec_telegram_links_code_hash", "sec_telegram_links", ["code_hash"], unique=True)
    op.create_index("ix_sec_telegram_links_subscription_id", "sec_telegram_links", ["subscription_id"])
    op.create_index("ix_sec_telegram_links_member_id", "sec_telegram_links", ["member_id"])


def downgrade() -> None:
    op.drop_index("ix_sec_telegram_links_member_id", "sec_telegram_links")
    op.drop_index("ix_sec_telegram_links_subscription_id", "sec_telegram_links")
    op.drop_index("ix_sec_telegram_links_code_hash", "sec_telegram_links")
    op.drop_table("sec_telegram_links")
    op.drop_index("ix_sec_property_members_telegram_chat_id", "sec_property_members")
    op.drop_column("sec_property_members", "telegram_linked_at")
    op.drop_column("sec_property_members", "telegram_chat_id")
