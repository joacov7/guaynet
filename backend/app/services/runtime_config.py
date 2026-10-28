"""
Settings editable from the admin panel (Seguridad → Configuración).

Values live in SystemConfig; secrets are stored encrypted with ENCRYPTION_KEY.
When a value is not set in the panel, the environment (.env) is used, so
existing installations keep working. Reads are cached for a short time so
sending a message does not hit the database every time; other processes
(workers, bot) pick up changes within CACHE_SECONDS.
"""
import time
from typing import Dict, List, Optional

from app.core.config import settings

CACHE_SECONDS = 30

TELEGRAM_TOKEN_KEY = "telegram_bot_token"          # encrypted
TELEGRAM_CHAT_IDS_KEY = "telegram_operator_chat_ids"  # comma separated

BEAT_API_URL_KEY = "beat_api_url"
BEAT_API_KEY_KEY = "beat_api_key"                 # encrypted
BEAT_WEBHOOK_SECRET_KEY = "beat_webhook_secret"   # encrypted
BEAT_DEFAULT_API_URL = "https://beat.netio.com.ar/api/v1"

# key → (default, min, max)
INT_PARAMS: Dict[str, tuple] = {
    "sec_confirmation_window_seconds": (180, 30, 900),
    "sec_entry_default_minutes": (5, 1, 30),
    "sec_schedule_default_tolerance": (15, 0, 180),
}

_cache: Dict[str, Optional[str]] = {}
_cache_at: float = 0.0


def invalidate_cache() -> None:
    global _cache_at
    _cache_at = 0.0


async def _load() -> Dict[str, Optional[str]]:
    global _cache, _cache_at
    if time.monotonic() - _cache_at < CACHE_SECONDS:
        return _cache
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.config import SystemConfig

    keys = [TELEGRAM_TOKEN_KEY, TELEGRAM_CHAT_IDS_KEY, BEAT_API_URL_KEY, BEAT_API_KEY_KEY,
            BEAT_WEBHOOK_SECRET_KEY, *INT_PARAMS]
    try:
        async with AsyncSessionLocal() as db:
            rows = await db.execute(select(SystemConfig).where(SystemConfig.key.in_(keys)))
            _cache = {r.key: r.value for r in rows.scalars().all()}
            _cache_at = time.monotonic()
    except Exception:
        # Database unavailable: keep the last known values (or env fallbacks)
        pass
    return _cache


def parse_chat_ids(raw: Optional[str]) -> List[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


async def telegram_token() -> str:
    from app.core.security import decrypt_value
    stored = (await _load()).get(TELEGRAM_TOKEN_KEY)
    if stored:
        return decrypt_value(stored)
    return settings.TELEGRAM_BOT_TOKEN


async def telegram_token_source() -> str:
    if (await _load()).get(TELEGRAM_TOKEN_KEY):
        return "panel"
    return "env" if settings.TELEGRAM_BOT_TOKEN else "none"


async def operator_chat_ids() -> List[int]:
    stored = (await _load()).get(TELEGRAM_CHAT_IDS_KEY)
    if stored:
        return parse_chat_ids(stored)
    return settings.telegram_allowed_ids_list


async def operator_chat_ids_source() -> str:
    if (await _load()).get(TELEGRAM_CHAT_IDS_KEY):
        return "panel"
    return "env" if settings.TELEGRAM_ALLOWED_CHAT_IDS else "none"


async def int_param(key: str) -> int:
    default, lo, hi = INT_PARAMS[key]
    raw = (await _load()).get(key)
    try:
        value = int(raw) if raw not in (None, "") else default
    except ValueError:
        value = default
    return max(lo, min(hi, value))


async def beat_api_url() -> str:
    return ((await _load()).get(BEAT_API_URL_KEY) or BEAT_DEFAULT_API_URL).rstrip("/")


async def _decrypted(key: str) -> str:
    from app.core.security import decrypt_value
    stored = (await _load()).get(key)
    return decrypt_value(stored) if stored else ""


async def beat_api_key() -> str:
    return await _decrypted(BEAT_API_KEY_KEY)


async def beat_webhook_secret() -> str:
    return await _decrypted(BEAT_WEBHOOK_SECRET_KEY)
