"""Security — includes_monitoring en planes y client_telegram_id en suscripciones

Revision ID: 027
Revises: 026
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sec_plans",
        sa.Column("includes_monitoring", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "sec_subscriptions",
        sa.Column("client_telegram_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sec_subscriptions", "client_telegram_id")
    op.drop_column("sec_plans", "includes_monitoring")
