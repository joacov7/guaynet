"""
BEAT (Netio) REST API client.

Based on Netio's own example code (apikey.py from their "Webhooks" tutorial):
- POST {base}/apikey/authenticate  body {"apikey": KEY}  → {"token": ...}
- GET  {base}/event/{event_id}     header Authorization: Bearer <token>

Unlike the example, TLS certificates are verified: disabling verification
would let anyone impersonate BEAT. The token lifetime is not documented, so it
is cached and requested again when BEAT answers 401.
"""
import re
import time
from typing import Any, Optional

import httpx

TIMEOUT = httpx.Timeout(15.0, connect=10.0)
TOKEN_CACHE_SECONDS = 600
# eventId comes from the (external) webhook and goes into the URL path
_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class BeatApiError(Exception):
    pass


_token: Optional[str] = None
_token_for: Optional[tuple] = None
_token_at: float = 0.0


def _forget_token() -> None:
    global _token, _token_for
    _token, _token_for = None, None


async def _config() -> tuple:
    from app.services import runtime_config as rc
    url, key = await rc.beat_api_url(), await rc.beat_api_key()
    if not key:
        raise BeatApiError("Falta la API key de BEAT (Seguridad → Config. Seguridad).")
    return url, key


async def authenticate(url: str, key: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(f"{url}/apikey/authenticate", json={"apikey": key})
    except httpx.ConnectError as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            raise BeatApiError("El certificado HTTPS de BEAT no es válido.")
        raise BeatApiError(f"No se pudo conectar con BEAT ({url}).")
    except httpx.TimeoutException:
        raise BeatApiError("BEAT no respondió a tiempo.")
    except httpx.RequestError as exc:
        raise BeatApiError(f"Error de red con BEAT: {type(exc).__name__}")

    if r.status_code in (401, 403):
        raise BeatApiError("BEAT rechazó la API key.")
    if r.status_code >= 400:
        raise BeatApiError(f"BEAT respondió {r.status_code} al autenticar.")
    try:
        token = r.json()["token"]
    except (ValueError, KeyError, TypeError):
        raise BeatApiError("Respuesta inesperada de BEAT al autenticar (no trae 'token').")
    if not token:
        raise BeatApiError("BEAT devolvió un token vacío.")
    return token


async def _get_token(url: str, key: str) -> str:
    global _token, _token_for, _token_at
    if _token and _token_for == (url, key) and time.monotonic() - _token_at < TOKEN_CACHE_SECONDS:
        return _token
    _token = await authenticate(url, key)
    _token_for, _token_at = (url, key), time.monotonic()
    return _token


async def get_event(event_id: str) -> Any:
    """Full event from BEAT. Retries once with a fresh token on 401."""
    event_id = str(event_id)
    if not _EVENT_ID_RE.match(event_id):
        raise BeatApiError("eventId con formato inválido.")
    url, key = await _config()
    for attempt in (1, 2):
        token = await _get_token(url, key)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.get(
                    f"{url}/event/{event_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.TimeoutException:
            raise BeatApiError("BEAT no respondió a tiempo.")
        except httpx.RequestError as exc:
            raise BeatApiError(f"Error de red con BEAT: {type(exc).__name__}")
        if r.status_code == 401 and attempt == 1:
            _forget_token()
            continue
        if r.status_code == 404:
            raise BeatApiError(f"BEAT no encontró el evento {event_id}.")
        if r.status_code >= 400:
            raise BeatApiError(f"BEAT respondió {r.status_code} al pedir el evento.")
        try:
            return r.json()
        except ValueError:
            raise BeatApiError("BEAT devolvió un evento que no es JSON.")
    raise BeatApiError("BEAT rechazó el token.")


async def test_connection() -> None:
    """Authenticate with the configured URL/key; raises BeatApiError on failure."""
    url, key = await _config()
    _forget_token()
    await _get_token(url, key)
