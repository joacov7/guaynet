"""security monthly reports: one report per subscription and period

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
    # The table, its columns and indexes already come from 026; this revision
    # only adds the one-report-per-period guarantee used by generate_and_deliver.
    op.create_unique_constraint(
        "uq_sec_monthly_report", "sec_monthly_reports", ["subscription_id", "period"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_sec_monthly_report", "sec_monthly_reports", type_="unique")
