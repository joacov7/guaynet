"""
BEAT (Netio) integration.

- POST /security/beat/webhook/{secret}: public receiver configured in BEAT →
  Avanzado → Webhooks. The secret in the URL is the only proof the call comes
  from BEAT (Netio does not document a signature). Capture mode: the
  notification is stored and the full event is fetched in background; no
  alerts are generated until the real event format is mapped.
- Admin endpoints: test the API key, get/regenerate the webhook URL, list
  captured notifications.
"""
import hmac
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, require_admin
from app.models.config import SystemConfig
from app.models.security.beat_webhook import SecurityBeatWebhook
from app.services import runtime_config as rc

router = APIRouter()

MAX_BODY_BYTES = 64 * 1024
WEBHOOK_PATH = "/api/v1/security/beat/webhook/"


def _webhook_url(secret: str) -> str:
    return f"{settings.PUBLIC_URL.rstrip('/')}{WEBHOOK_PATH}{secret}"


@router.post("/webhook/{secret}")
async def receive_webhook(secret: str, request: Request, db: AsyncSession = Depends(get_db)):
    expected = await rc.beat_webhook_secret()
    if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
        # Same answer as an unknown route: do not reveal that the endpoint exists
        raise HTTPException(status_code=404, detail="Not Found")

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload demasiado grande")
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        payload = {"_raw": body[:4000].decode("utf-8", errors="replace")}

    event_id = payload.get("eventId") if isinstance(payload, dict) else None
    event_type = payload.get("type") if isinstance(payload, dict) else None

    from app.api.v1.endpoints.portal import _client_ip
    row = SecurityBeatWebhook(
        remote_ip=_client_ip(request) or None,
        payload=payload,
        event_id=str(event_id)[:64] if event_id is not None else None,
        event_type=str(event_type)[:100] if event_type is not None else None,
        fetch_status="pending" if event_id is not None else "no_event_id",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    if event_id is not None:
        try:
            from app.tasks.security import fetch_beat_event
            fetch_beat_event.delay(row.id)
        except Exception as exc:
            row.fetch_status, row.fetch_error = "error", f"No se pudo encolar la consulta: {type(exc).__name__}"
            await db.commit()

    # BEAT only needs a 200; same body as Netio's example receiver
    return {"status": "success", "message": "Webhook recibido correctamente"}


@router.get("/webhook-url")
async def get_webhook_url(_=Depends(require_admin)):
    rc.invalidate_cache()
    secret = await rc.beat_webhook_secret()
    return {"webhook_url": _webhook_url(secret) if secret else None}


@router.post("/webhook-url")
async def regenerate_webhook_url(_=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Create (or replace) the secret. The old URL stops working immediately."""
    from app.core.security import encrypt_value

    secret = secrets.token_urlsafe(32)
    row = await db.get(SystemConfig, rc.BEAT_WEBHOOK_SECRET_KEY)
    if row:
        row.value = encrypt_value(secret)
    else:
        db.add(SystemConfig(key=rc.BEAT_WEBHOOK_SECRET_KEY, value=encrypt_value(secret)))
    await db.commit()
    rc.invalidate_cache()
    return {"webhook_url": _webhook_url(secret)}


@router.post("/test-connection")
async def test_connection(_=Depends(require_admin)):
    from app.services.security.beat_api import BeatApiError, test_connection as _test

    rc.invalidate_cache()
    try:
        await _test()
    except BeatApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"ok": True, "api_url": await rc.beat_api_url()}


@router.get("/webhooks")
async def list_webhooks(
    limit: int = 30,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SecurityBeatWebhook)
        .order_by(SecurityBeatWebhook.id.desc())
        .limit(max(1, min(limit, 200)))
    )
    return [
        {
            "id": w.id,
            "received_at": w.received_at.isoformat() if w.received_at else None,
            "remote_ip": w.remote_ip,
            "event_id": w.event_id,
            "event_type": w.event_type,
            "fetch_status": w.fetch_status,
            "fetch_error": w.fetch_error,
            "payload": w.payload,
            "event_detail": w.event_detail,
        }
        for w in result.scalars().all()
    ]
