"""Security — configuración de check-in adultos mayores

Revision ID: 033
Revises: 032
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_elderly_configs",
        sa.Column("id",                  sa.Integer(),    primary_key=True),
        sa.Column("subscription_id",     sa.Integer(),    nullable=False),
        sa.Column("check_from",          sa.String(5),    nullable=False, server_default="07:00"),
        sa.Column("check_until",         sa.String(5),    nullable=False, server_default="10:00"),
        sa.Column("notify_telegram_id",  sa.String(100),  nullable=True),
        sa.Column("enabled",             sa.Boolean(),    nullable=False, server_default="true"),
        sa.Column("created_at",          sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",          sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["subscription_id"], ["sec_subscriptions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("subscription_id", name="uq_sec_elderly_sub"),
    )
    op.create_index("ix_sec_elderly_sub", "sec_elderly_configs", ["subscription_id"])


def downgrade() -> None:
    op.drop_table("sec_elderly_configs")
