"""per-user permission overrides

Revision ID: 023
Revises: 022
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("section", sa.String(50), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("can_edit", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("user_id", "section", name="uq_user_section"),
    )


def downgrade():
    op.drop_table("user_permissions")
