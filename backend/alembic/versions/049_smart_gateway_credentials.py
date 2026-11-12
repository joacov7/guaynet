"""Add hashed credentials for Smart gateways.

Revision ID: 049
Revises: 048
"""
from alembic import op
import sqlalchemy as sa

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("smart_gateways", sa.Column("credential_hash", sa.String(64), nullable=True))
    op.add_column("smart_gateways", sa.Column("credential_rotated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("uq_smart_gateway_credential_hash", "smart_gateways", ["credential_hash"], unique=True, postgresql_where=sa.text("credential_hash IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_smart_gateway_credential_hash", table_name="smart_gateways")
    op.drop_column("smart_gateways", "credential_rotated_at")
    op.drop_column("smart_gateways", "credential_hash")
