"""portal_and_automations

Revision ID: 011
Revises: 010
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("portal_enabled", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("clients", sa.Column("portal_password_hash", sa.String(255), nullable=True))

    op.create_table(
        "automation_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("affected", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table("automation_logs")
    op.drop_column("clients", "portal_password_hash")
    op.drop_column("clients", "portal_enabled")
