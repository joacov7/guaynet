"""system config table

Revision ID: 006
Revises: 005
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

DEFAULTS = [
    ("suspension_action", "disable"),   # disable | throttle
    ("suspension_speed", "64k"),        # MikroTik max-limit string when throttling
]


def upgrade():
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
    )
    op.bulk_insert(
        sa.table("system_config",
                 sa.column("key", sa.String),
                 sa.column("value", sa.Text)),
        [{"key": k, "value": v} for k, v in DEFAULTS],
    )


def downgrade():
    op.drop_table("system_config")
