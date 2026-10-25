"""ubiquiti_ac_types

Revision ID: 013
Revises: 012
Create Date: 2026-10-15
"""
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE ubiquitidevicetype ADD VALUE IF NOT EXISTS 'airmax_ac_ap'")
    op.execute("ALTER TYPE ubiquitidevicetype ADD VALUE IF NOT EXISTS 'airmax_ac_station'")


def downgrade():
    pass
