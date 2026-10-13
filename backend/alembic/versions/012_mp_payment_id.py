"""add mp_payment_id to invoices

Revision ID: 012
Revises: 011
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("mp_payment_id", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("invoices", "mp_payment_id")
