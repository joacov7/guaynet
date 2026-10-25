"""security weekly opening schedules

Revision ID: 037
Revises: 036
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("sec_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.Column("tolerance_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("subscription_id", "weekday", name="uq_sec_schedule_day"),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_sec_schedule_weekday"),
        sa.CheckConstraint("open_time < close_time", name="ck_sec_schedule_times"),
    )
    op.create_index("ix_sec_schedules_subscription_id", "sec_schedules", ["subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_sec_schedules_subscription_id", "sec_schedules")
    op.drop_table("sec_schedules")
