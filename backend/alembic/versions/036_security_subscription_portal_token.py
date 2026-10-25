"""security subscription portal token

Revision ID: 036
Revises: 035
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sec_subscriptions",
        sa.Column("portal_token", sa.String(64), nullable=True),
    )
    op.create_unique_constraint("uq_sec_subscriptions_portal_token", "sec_subscriptions", ["portal_token"])
    op.create_index("ix_sec_subscriptions_portal_token", "sec_subscriptions", ["portal_token"])


def downgrade() -> None:
    op.drop_index("ix_sec_subscriptions_portal_token", "sec_subscriptions")
    op.drop_constraint("uq_sec_subscriptions_portal_token", "sec_subscriptions")
    op.drop_column("sec_subscriptions", "portal_token")
