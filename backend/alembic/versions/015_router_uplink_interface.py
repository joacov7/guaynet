"""router uplink interface for Queue Tree QoS

Revision ID: 015
Revises: 014
Create Date: 2026-10-17
"""
import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mikrotik_routers", sa.Column("uplink_interface", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("mikrotik_routers", "uplink_interface")
