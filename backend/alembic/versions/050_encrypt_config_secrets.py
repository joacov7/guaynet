"""config: encrypt secrets stored in system_config

MercadoPago, Twilio, SMTP and AFIP credentials were stored in plain text. They
are now kept as "enc:<fernet token>" with ENCRYPTION_KEY (app/services/config_secrets.py).
Data-only migration; values already encrypted are left alone.

Revision ID: 050
Revises: 049
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None

KEYS = ("twilio_auth_token", "smtp_password", "mp_access_token", "mp_webhook_secret", "afip_key_pem")


def _rows(conn):
    return conn.execute(
        sa.text("SELECT key, value FROM system_config WHERE key IN :keys").bindparams(sa.bindparam("keys", expanding=True)),
        {"keys": list(KEYS)},
    ).fetchall()


def upgrade() -> None:
    from app.services.config_secrets import PREFIX, seal

    conn = op.get_bind()
    for key, value in _rows(conn):
        if value and not value.startswith(PREFIX):
            conn.execute(sa.text("UPDATE system_config SET value = :v WHERE key = :k"), {"v": seal(value), "k": key})


def downgrade() -> None:
    from app.services.config_secrets import PREFIX, unseal

    conn = op.get_bind()
    for key, value in _rows(conn):
        if value and value.startswith(PREFIX):
            conn.execute(sa.text("UPDATE system_config SET value = :v WHERE key = :k"), {"v": unseal(value), "k": key})
