"""inventory_items

Revision ID: 009
Revises: 008
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False, index=True),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("serial_number", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("condition", sa.Enum("new", "good", "damaged", "scrapped", name="equipmentcondition"), nullable=False, server_default="new"),
        sa.Column("status", sa.Enum("in_stock", "assigned", "returned", "lost", name="equipmentstatus"), nullable=False, server_default="in_stock"),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_inventory_items_status", "inventory_items", ["status"])


def downgrade():
    op.drop_table("inventory_items")
    op.execute("DROP TYPE IF EXISTS equipmentcondition")
    op.execute("DROP TYPE IF EXISTS equipmentstatus")
