"""add zone_id to clients

Revision ID: 018
Revises: 017
Create Date: 2026-10-18

"""
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("clients", sa.Column("zone_id", sa.Integer(), sa.ForeignKey("zones.id"), nullable=True))
    op.create_index("ix_clients_zone_id", "clients", ["zone_id"])


def downgrade():
    op.drop_index("ix_clients_zone_id", table_name="clients")
    op.drop_column("clients", "zone_id")
