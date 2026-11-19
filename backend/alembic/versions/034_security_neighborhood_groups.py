"""security neighborhood groups

Revision ID: 034
Revises: 033
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_neighborhood_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("telegram_group_id", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "sec_neighborhood_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("sec_neighborhood_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("subscription_id", name="uq_neighborhood_membership_subscription"),
    )
    op.create_index("ix_sec_neighborhood_memberships_group_id", "sec_neighborhood_memberships", ["group_id"])
    op.create_index("ix_sec_neighborhood_memberships_subscription_id", "sec_neighborhood_memberships", ["subscription_id"])


def downgrade() -> None:
    op.drop_table("sec_neighborhood_memberships")
    op.drop_table("sec_neighborhood_groups")
