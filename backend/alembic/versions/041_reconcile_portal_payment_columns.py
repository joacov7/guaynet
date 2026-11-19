"""reconcile columns from 011/012 on databases built with the old placeholders

Revision ID: 041
Revises: 040

This branch used to ship empty placeholder migrations 011 and 012. A database
created from it is stamped past 012 without the portal, automation and
MercadoPago columns. This migration adds them only when missing, so it is a
no-op on databases that ran the real 011/012.
"""
from alembic import op

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS portal_enabled BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS portal_password_hash VARCHAR(255)")
    op.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS mp_payment_id VARCHAR(100)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_logs (
            id SERIAL PRIMARY KEY,
            job VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL,
            message TEXT,
            affected INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_automation_logs_job ON automation_logs (job)")


def downgrade() -> None:
    # Nothing to undo: on databases that ran the real 011/012 these objects
    # belong to those migrations.
    pass
