"""Security — certificados de protección para seguros

Revision ID: 032
Revises: 031
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_certificates",
        sa.Column("id",                 sa.Integer(),                     primary_key=True),
        sa.Column("subscription_id",    sa.Integer(),                     nullable=False),
        sa.Column("issued_at",          sa.DateTime(timezone=True),       nullable=False),
        sa.Column("valid_until",        sa.DateTime(timezone=True),       nullable=False),
        sa.Column("verification_token", sa.String(64),                    nullable=False),
        sa.Column("file_path",          sa.String(500),                   nullable=True),
        sa.Column("created_at",         sa.DateTime(timezone=True),       nullable=True),
        sa.Column("updated_at",         sa.DateTime(timezone=True),       nullable=True),
        sa.ForeignKeyConstraint(["subscription_id"], ["sec_subscriptions.id"]),
        sa.UniqueConstraint("subscription_id",    name="uq_sec_cert_subscription"),
        sa.UniqueConstraint("verification_token", name="uq_sec_cert_token"),
    )
    op.create_index("ix_sec_cert_sub",   "sec_certificates", ["subscription_id"])
    op.create_index("ix_sec_cert_token", "sec_certificates", ["verification_token"])


def downgrade() -> None:
    op.drop_table("sec_certificates")
