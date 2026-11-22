"""clients: dated notes with author (ficha del cliente)

Revision ID: 052
Revises: 051
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_client_notes_client_id", "client_notes", ["client_id"])
    op.create_index("ix_client_notes_created_at", "client_notes", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_client_notes_created_at", "client_notes")
    op.drop_index("ix_client_notes_client_id", "client_notes")
    op.drop_table("client_notes")
