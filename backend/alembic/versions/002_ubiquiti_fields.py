"""Add extended fields to ubiquiti_devices

Revision ID: 002
Revises: 001
Create Date: 2026-05-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ubiquiti_devices", sa.Column("model_name", sa.String(100), nullable=True))
    op.add_column("ubiquiti_devices", sa.Column("firmware_version", sa.String(100), nullable=True))
    op.add_column("ubiquiti_devices", sa.Column("ssid", sa.String(100), nullable=True))
    op.add_column("ubiquiti_devices", sa.Column("frequency_mhz", sa.Integer(), nullable=True))
    op.add_column("ubiquiti_devices", sa.Column("channel_width_mhz", sa.Integer(), nullable=True))
    op.add_column("ubiquiti_devices", sa.Column("signal_dbm", sa.Integer(), nullable=True))
    op.add_column("ubiquiti_devices", sa.Column("ccq", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ubiquiti_devices", "ccq")
    op.drop_column("ubiquiti_devices", "signal_dbm")
    op.drop_column("ubiquiti_devices", "channel_width_mhz")
    op.drop_column("ubiquiti_devices", "frequency_mhz")
    op.drop_column("ubiquiti_devices", "ssid")
    op.drop_column("ubiquiti_devices", "firmware_version")
    op.drop_column("ubiquiti_devices", "model_name")
