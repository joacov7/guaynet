"""Security — campos de confirmación de alerta en sec_alerts

Revision ID: 028
Revises: 027
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sec_alerts", sa.Column("confirmation_sent_at",     sa.DateTime(timezone=True), nullable=True))
    op.add_column("sec_alerts", sa.Column("confirmation_expires_at",  sa.DateTime(timezone=True), nullable=True))
    op.add_column("sec_alerts", sa.Column("confirmation_telegram_msg_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("sec_alerts", "confirmation_telegram_msg_id")
    op.drop_column("sec_alerts", "confirmation_expires_at")
    op.drop_column("sec_alerts", "confirmation_sent_at")
