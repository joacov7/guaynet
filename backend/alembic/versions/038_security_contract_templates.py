"""security contract templates and portal acceptance fields

Revision ID: 038
Revises: 037
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_contract_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(20), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # At most one active template
    op.create_index(
        "uq_sec_contract_templates_active", "sec_contract_templates", ["is_active"],
        unique=True, postgresql_where=sa.text("is_active"),
    )

    op.alter_column("sec_contracts", "accepted_by_user_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("sec_contracts", sa.Column("template_id", sa.Integer(), sa.ForeignKey("sec_contract_templates.id"), nullable=True))
    op.create_index("ix_sec_contracts_template_id", "sec_contracts", ["template_id"])
    op.add_column("sec_contracts", sa.Column("signer_name", sa.String(150), nullable=True))
    op.add_column("sec_contracts", sa.Column("signer_dni", sa.String(20), nullable=True))
    op.add_column("sec_contracts", sa.Column("method", sa.String(30), nullable=True))
    op.add_column("sec_contracts", sa.Column("pdf_path", sa.String(500), nullable=True))
    # One acceptance per subscription and contract version
    op.create_unique_constraint("uq_sec_contracts_sub_version", "sec_contracts", ["subscription_id", "version"])


def downgrade() -> None:
    op.drop_constraint("uq_sec_contracts_sub_version", "sec_contracts")
    op.drop_column("sec_contracts", "pdf_path")
    op.drop_column("sec_contracts", "method")
    op.drop_column("sec_contracts", "signer_dni")
    op.drop_column("sec_contracts", "signer_name")
    op.drop_index("ix_sec_contracts_template_id", "sec_contracts")
    op.drop_column("sec_contracts", "template_id")
    # Only safe if no portal acceptances (accepted_by_user_id NULL) exist
    op.alter_column("sec_contracts", "accepted_by_user_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("uq_sec_contract_templates_active", "sec_contract_templates")
    op.drop_table("sec_contract_templates")
