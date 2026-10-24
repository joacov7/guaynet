"""Security — tabla de reportes semanales

Revision ID: 029
Revises: 028
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_weekly_reports",
        sa.Column("id",                   sa.Integer(),                          nullable=False),
        sa.Column("subscription_id",      sa.Integer(),                          nullable=False),
        sa.Column("week_label",           sa.String(10),                         nullable=False),
        sa.Column("period_start",         sa.DateTime(timezone=True),            nullable=False),
        sa.Column("period_end",           sa.DateTime(timezone=True),            nullable=False),
        sa.Column("generated_at",         sa.DateTime(timezone=True),            nullable=True),
        sa.Column("sent_at",              sa.DateTime(timezone=True),            nullable=True),
        sa.Column("event_count",          sa.Integer(),  server_default="0",     nullable=False),
        sa.Column("armed_count",          sa.Integer(),  server_default="0",     nullable=False),
        sa.Column("disarmed_count",       sa.Integer(),  server_default="0",     nullable=False),
        sa.Column("alert_count",          sa.Integer(),  server_default="0",     nullable=False),
        sa.Column("test_count",           sa.Integer(),  server_default="0",     nullable=False),
        sa.Column("battery_warning_count",sa.Integer(),  server_default="0",     nullable=False),
        sa.Column("battery_warnings",     sa.JSON(),                             nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["subscription_id"], ["sec_subscriptions.id"]),
        sa.UniqueConstraint("subscription_id", "week_label", name="uq_sec_weekly_report"),
    )
    op.create_index("ix_sec_weekly_reports_subscription_id", "sec_weekly_reports", ["subscription_id"])
    op.create_index("ix_sec_weekly_reports_week_label",      "sec_weekly_reports", ["week_label"])


def downgrade() -> None:
    op.drop_index("ix_sec_weekly_reports_week_label",      table_name="sec_weekly_reports")
    op.drop_index("ix_sec_weekly_reports_subscription_id", table_name="sec_weekly_reports")
    op.drop_table("sec_weekly_reports")
