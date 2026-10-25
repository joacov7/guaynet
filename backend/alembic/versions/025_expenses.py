"""expenses table

Revision ID: 025
Revises: 024
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "hosting", "equipment", "energy", "labor", "internet",
                "transport", "software", "maintenance", "other",
                name="expensecategory",
            ),
            nullable=False,
            server_default="other",
        ),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_expenses_expense_date", "expenses", ["expense_date"])


def downgrade():
    op.drop_index("ix_expenses_expense_date", table_name="expenses")
    op.drop_table("expenses")
    op.execute("DROP TYPE IF EXISTS expensecategory")
