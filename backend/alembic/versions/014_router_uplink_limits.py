"""router uplink limits

Revision ID: 014
Revises: 013
Create Date: 2026-10-16
"""
import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mikrotik_routers", sa.Column("uplink_download_mbps", sa.Integer(), nullable=True))
    op.add_column("mikrotik_routers", sa.Column("uplink_upload_mbps", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("mikrotik_routers", "uplink_upload_mbps")
    op.drop_column("mikrotik_routers", "uplink_download_mbps")
