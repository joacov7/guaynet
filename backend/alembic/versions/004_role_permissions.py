"""role permissions table

Revision ID: 004
Revises: 003
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role", sa.String(20), nullable=False, index=True),
        sa.Column("section", sa.String(50), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("can_edit", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("role", "section", name="uq_role_section"),
    )

    # Also add 'technician' as valid role comment in users (no constraint change needed)


def downgrade():
    op.drop_table("role_permissions")
