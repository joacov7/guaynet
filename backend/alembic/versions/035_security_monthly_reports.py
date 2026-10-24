"""security monthly reports table

Revision ID: 035
Revises: 034
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_monthly_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("sec_subscriptions.id"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),  # YYYY-MM
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="generating",
        ),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alert_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("test_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.UniqueConstraint("subscription_id", "period", name="uq_sec_monthly_report"),
    )
    op.create_index("ix_sec_monthly_reports_subscription_id", "sec_monthly_reports", ["subscription_id"])
    op.create_index("ix_sec_monthly_reports_period", "sec_monthly_reports", ["period"])


def downgrade() -> None:
    op.drop_table("sec_monthly_reports")
