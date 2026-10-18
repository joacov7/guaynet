"""create zones table

Revision ID: 017
Revises: 016
Create Date: 2026-10-18

"""
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(20), nullable=False, server_default="#1677ff"),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("mikrotik_routers.id"), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zones_name", "zones", ["name"], unique=True)


def downgrade():
    op.drop_index("ix_zones_name", table_name="zones")
    op.drop_table("zones")
