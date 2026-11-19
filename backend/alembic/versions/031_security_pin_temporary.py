"""Security — PIN temporal con expiración

Revision ID: 031
Revises: 030
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pin_type is stored as VARCHAR (native_enum=False), no enum DDL needed.
    op.add_column("sec_pin_credentials", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sec_pin_credentials", sa.Column("label",      sa.String(100),               nullable=True))


def downgrade() -> None:
    op.drop_column("sec_pin_credentials", "label")
    op.drop_column("sec_pin_credentials", "expires_at")
