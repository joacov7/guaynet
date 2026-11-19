"""Security — cortes de luz en reportes semanales

Revision ID: 030
Revises: 029
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sec_weekly_reports", sa.Column("power_failure_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("sec_weekly_reports", sa.Column("power_failures",      sa.JSON(),    nullable=True))


def downgrade() -> None:
    op.drop_column("sec_weekly_reports", "power_failures")
    op.drop_column("sec_weekly_reports", "power_failure_count")
