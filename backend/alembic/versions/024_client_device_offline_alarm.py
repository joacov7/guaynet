"""add client_device_offline alarm type

Revision ID: 024
Revises: 023
Create Date: 2026-10-22
"""
from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade():
    # AlarmType uses native_enum=False (VARCHAR) — no schema change needed.
    pass


def downgrade():
    pass
