"""router lan interface for Queue Tree download QoS

Revision ID: 016
Revises: 015
Create Date: 2026-10-17
"""
import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mikrotik_routers", sa.Column("lan_interface", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("mikrotik_routers", "lan_interface")
