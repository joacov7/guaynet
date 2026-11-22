"""
Secrets kept in system_config (Configuración del sistema): stored encrypted with
ENCRYPTION_KEY as "enc:<fernet token>", never returned by the config API.
Values saved before this existed are plain text and still readable (migration 050
encrypts them).
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

SECRET_KEYS = frozenset({
    "twilio_auth_token",
    "smtp_password",
    "mp_access_token",
    "mp_webhook_secret",
    "afip_key_pem",
})
PREFIX = "enc:"


def seal(value: str) -> str:
    from cryptography.fernet import Fernet

    from app.core.config import settings

    if not settings.ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY is not set: secrets cannot be stored")
    return PREFIX + Fernet(settings.ENCRYPTION_KEY.encode()).encrypt(value.encode()).decode()


def unseal(stored: Optional[str]) -> str:
    if not stored:
        return ""
    if not stored.startswith(PREFIX):
        return stored  # saved before encryption existed
    from cryptography.fernet import Fernet, InvalidToken

    from app.core.config import settings

    try:
        return Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(stored[len(PREFIX):].encode()).decode()
    except (InvalidToken, ValueError) as exc:
        # Wrong/rotated ENCRYPTION_KEY: fail loudly instead of sending the ciphertext as a password
        raise RuntimeError("No se pudo descifrar un secreto de la configuración (¿cambió ENCRYPTION_KEY?)") from exc


async def config_value(db: AsyncSession, key: str, default: str = "") -> str:
    """A system_config value, decrypted when it is a secret."""
    from app.models.config import SystemConfig

    row = await db.get(SystemConfig, key)
    if not row or row.value is None:
        return default
    return unseal(row.value) if key in SECRET_KEYS else row.value
