"""payments: cuenta corriente (saldo a favor, quién cobró, anulación)

- client_id on every payment (filled from its invoice), so a payment can exist
  without an invoice: that is saldo a favor, applied to the next invoices.
- group_id joins the rows of one collection split across invoices.
- received_by_*: who collected it. voided_*: a voided payment stays on record.
Existing payments: client from their invoice, each its own group, MercadoPago
ones marked as collected by "MercadoPago". No data is removed.

Revision ID: 053
Revises: 052
Create Date: 2026-11-23
"""
from alembic import op
import sqlalchemy as sa

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True))
    op.add_column("payments", sa.Column("group_id", sa.String(36), nullable=True))
    op.add_column("payments", sa.Column("received_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("payments", sa.Column("received_by_name", sa.String(100), nullable=True))
    op.add_column("payments", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("voided_by_name", sa.String(100), nullable=True))
    op.add_column("payments", sa.Column("void_reason", sa.Text(), nullable=True))

    op.execute("UPDATE payments p SET client_id = i.client_id FROM invoices i WHERE i.id = p.invoice_id")
    op.execute("UPDATE payments SET group_id = 'p' || id WHERE group_id IS NULL")
    op.execute("UPDATE payments SET received_by_name = 'MercadoPago' WHERE method = 'mercadopago' AND received_by_name IS NULL")

    op.alter_column("payments", "client_id", nullable=False)
    op.alter_column("payments", "invoice_id", existing_type=sa.Integer(), nullable=True)
    op.create_index("ix_payments_client_id", "payments", ["client_id"])
    op.create_index("ix_payments_group_id", "payments", ["group_id"])
    op.create_index("ix_payments_payment_date", "payments", ["payment_date"])


def downgrade() -> None:
    # The old table cannot hold saldo a favor (no invoice) nor tell a voided payment
    # apart (it would count again): those rows go. Only for a manual rollback.
    op.execute("DELETE FROM payments WHERE invoice_id IS NULL OR voided_at IS NOT NULL")
    op.drop_index("ix_payments_payment_date", table_name="payments")
    op.drop_index("ix_payments_group_id", table_name="payments")
    op.drop_index("ix_payments_client_id", table_name="payments")
    op.alter_column("payments", "invoice_id", existing_type=sa.Integer(), nullable=False)
    for col in ("void_reason", "voided_by_name", "voided_at", "received_by_name", "received_by_id", "group_id", "client_id"):
        op.drop_column("payments", col)
