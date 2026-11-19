"""security schedule: track late-opening notice

Revision ID: 039
Revises: 038
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sec_schedules", sa.Column("not_opened_notified_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("sec_schedules", "not_opened_notified_on")
