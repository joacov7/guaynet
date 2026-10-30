import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

_INSECURE_KEYS = {
    "dev-secret-key-change-in-production",
    "changeme",
    "secret",
    "",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    APP_NAME: str = "Guaynet WISP"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ENCRYPTION_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    DATABASE_URL: str = "postgresql+asyncpg://guaynet:guaynet@localhost:5432/guaynet"
    REDIS_URL: str = "redis://localhost:6379/0"

    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    FIRST_SUPERUSER: str = "admin"
    FIRST_SUPERUSER_PASSWORD: str = "changeme"
    FIRST_SUPERUSER_EMAIL: str = "admin@guaynet.local"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ALLOWED_CHAT_IDS: str = ""

    UPLOADS_DIR: str = "uploads"

    # Firebase Cloud Messaging (mobile app push). Path to the service account
    # JSON downloaded from Firebase. Empty = simulated push adapter (logs only).
    FCM_SERVICE_ACCOUNT_FILE: str = ""
    PUBLIC_URL: str = "https://guaynet.local"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def telegram_allowed_ids_list(self) -> List[int]:
        if not self.TELEGRAM_ALLOWED_CHAT_IDS:
            return []
        return [int(x.strip()) for x in self.TELEGRAM_ALLOWED_CHAT_IDS.split(",") if x.strip()]


def _is_placeholder(value: str) -> bool:
    """True for the sample values shipped in .env.example ("your-secret-key-here...", "your-fernet-key-here")."""
    return value.strip().lower().startswith("your-")


def check_security(cfg: "Settings") -> None:
    """Fail fast if the secrets are missing, default or copied verbatim from .env.example.

    Raises RuntimeError with the fix in the message. Skipped entirely when
    GUAYNET_SKIP_SECURITY_CHECK is set (local development only).
    """
    if cfg.SECRET_KEY in _INSECURE_KEYS or _is_placeholder(cfg.SECRET_KEY):
        raise RuntimeError(
            "SECRET_KEY is not set or uses a default/sample value: anyone could forge login tokens. "
            "Generate one with: openssl rand -hex 32"
        )
    fernet_hint = (
        "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )
    if not cfg.ENCRYPTION_KEY:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Credentials would be stored in plain text. " + fernet_hint
        )
    if _is_placeholder(cfg.ENCRYPTION_KEY):
        raise RuntimeError("ENCRYPTION_KEY is still the sample value from .env.example. " + fernet_hint)
    try:
        from cryptography.fernet import Fernet

        Fernet(cfg.ENCRYPTION_KEY.encode())
    except Exception as exc:  # invalid base64 / wrong length
        raise RuntimeError(
            "ENCRYPTION_KEY is not a valid Fernet key (it would fail the first time a credential is saved). " + fernet_hint
        ) from exc


def check_initial_admin_password(cfg: "Settings") -> None:
    """Refuse to create the first admin with a default/sample password. Same escape hatch as check_security."""
    if os.getenv("GUAYNET_SKIP_SECURITY_CHECK"):
        return
    if cfg.FIRST_SUPERUSER_PASSWORD in _INSECURE_KEYS or _is_placeholder(cfg.FIRST_SUPERUSER_PASSWORD):
        raise RuntimeError(
            "FIRST_SUPERUSER_PASSWORD is empty or a default value, and the admin user does not exist yet. "
            "Set a real password in .env before the first start (an existing admin is not affected)."
        )


settings = Settings()

# Fail fast in production if insecure defaults are present.
# Set GUAYNET_SKIP_SECURITY_CHECK=1 only in local development.
if not os.getenv("GUAYNET_SKIP_SECURITY_CHECK"):
    check_security(settings)
