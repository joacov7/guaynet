import asyncio
import base64
import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.config import SystemConfig
from app.models.push_subscription import PushSubscription
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# VAPID key helpers
# ---------------------------------------------------------------------------

def _generate_vapid_keypair() -> tuple[str, str]:
    from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    private_key = generate_private_key(SECP256R1())
    private_pem = private_key.private_bytes(
        Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
    ).decode()
    pub_bytes = private_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()
    return private_pem, public_b64


async def _get_or_create_vapid_keys(db: AsyncSession) -> tuple[str, str]:
    priv_row = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "vapid_private_key")
    )).scalar_one_or_none()
    pub_row = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "vapid_public_key")
    )).scalar_one_or_none()

    if priv_row and pub_row:
        return priv_row.value, pub_row.value

    private_pem, public_b64 = _generate_vapid_keypair()
    db.add(SystemConfig(key="vapid_private_key", value=private_pem))
    db.add(SystemConfig(key="vapid_public_key", value=public_b64))
    await db.commit()
    return private_pem, public_b64


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/vapid-key")
async def get_vapid_key(db: AsyncSession = Depends(get_db)):
    _, public_b64 = await _get_or_create_vapid_keys(db)
    return {"public_key": public_b64}


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscriptionRequest(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


@router.post("/subscribe", status_code=204)
async def subscribe(
    body: SubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = (await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )).scalar_one_or_none()

    if existing:
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
        existing.user_id = user.id
    else:
        db.add(PushSubscription(
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
        ))
    await db.commit()


@router.delete("/subscribe", status_code=204)
async def unsubscribe(
    body: SubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == body.endpoint,
            PushSubscription.user_id == user.id,
        )
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Internal helper — called from tickets endpoint on assignment
# ---------------------------------------------------------------------------

async def send_push_to_user(user_id: int, title: str, body_text: str, url: str, db: AsyncSession):
    try:
        from pywebpush import WebPushException, webpush

        subs = (await db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )).scalars().all()

        if not subs:
            return

        private_pem, _ = await _get_or_create_vapid_keys(db)
        payload = json.dumps({"title": title, "body": body_text, "url": url, "tag": "ticket"})

        dead: list[PushSubscription] = []
        for sub in subs:
            try:
                await asyncio.to_thread(
                    webpush,
                    subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=payload,
                    vapid_private_key=private_pem,
                    vapid_claims={"sub": "mailto:admin@guaynet.local"},
                )
            except WebPushException as ex:
                if ex.response and ex.response.status_code in (404, 410):
                    dead.append(sub)
                else:
                    logger.warning("Push failed for sub %s: %s", sub.id, ex)

        for sub in dead:
            await db.delete(sub)
        if dead:
            await db.commit()

    except Exception:
        logger.exception("send_push_to_user failed silently")
