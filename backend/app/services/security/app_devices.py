"""
Mobile app device linking and authentication.

A device is linked once with the portal link + alarm PIN and receives its own
random secret (shown only once, stored hashed). It then authenticates with
`Authorization: Device <device_id>.<secret>` and can be revoked individually.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.security.app_device import SecurityAppDevice
from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus

MAX_DEVICES_PER_SUBSCRIPTION = 10
# Lets the app tell "this phone was unlinked" apart from other 401s (wrong PIN)
_REVOKED_HEADERS = {"X-Device-Revoked": "1"}
_LAST_SEEN_RESOLUTION = timedelta(minutes=5)


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


async def pair_device(
    db: AsyncSession, subscription_id: int, device_name: str, platform: str
) -> Tuple[SecurityAppDevice, str]:
    active = await db.execute(
        select(SecurityAppDevice.id).where(
            SecurityAppDevice.subscription_id == subscription_id,
            SecurityAppDevice.revoked_at.is_(None),
        )
    )
    if len(active.all()) >= MAX_DEVICES_PER_SUBSCRIPTION:
        raise HTTPException(
            status_code=409,
            detail="Se alcanzó el máximo de teléfonos vinculados. Desvinculá alguno desde la central.",
        )
    secret = secrets.token_urlsafe(32)
    device = SecurityAppDevice(
        subscription_id=subscription_id,
        device_name=device_name.strip()[:100] or "Teléfono",
        platform=platform,
        secret_hash=_hash(secret),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device, secret


def parse_device_header(authorization: Optional[str]) -> Optional[Tuple[int, str]]:
    if not authorization or not authorization.startswith("Device "):
        return None
    raw = authorization[len("Device "):].strip()
    dev_id, _, secret = raw.partition(".")
    if not dev_id.isdigit() or not secret:
        raise HTTPException(status_code=401, detail="Credencial de dispositivo inválida", headers=_REVOKED_HEADERS)
    return int(dev_id), secret


async def authenticate_device(
    db: AsyncSession, authorization: Optional[str]
) -> Optional[Tuple[SecurityAppDevice, SecuritySubscription]]:
    """
    Returns (device, subscription) when the header carries a device credential,
    None when it carries none. Raises 401 for invalid or revoked credentials.
    """
    parsed = parse_device_header(authorization)
    if parsed is None:
        return None
    dev_id, secret = parsed
    device = await db.get(SecurityAppDevice, dev_id)
    valid = device is not None and hmac.compare_digest(device.secret_hash, _hash(secret))
    if not valid or device.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Este teléfono ya no está vinculado", headers=_REVOKED_HEADERS)

    result = await db.execute(
        select(SecuritySubscription)
        .options(selectinload(SecuritySubscription.features))
        .where(
            SecuritySubscription.id == device.subscription_id,
            SecuritySubscription.status == SecuritySubscriptionStatus.active,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=403, detail="La suscripción no está activa")

    now = datetime.now(timezone.utc)
    if device.last_seen_at is None or now - device.last_seen_at > _LAST_SEEN_RESOLUTION:
        device.last_seen_at = now
        await db.commit()
    return device, sub


async def list_devices(db: AsyncSession, subscription_id: int) -> List[SecurityAppDevice]:
    result = await db.execute(
        select(SecurityAppDevice)
        .where(SecurityAppDevice.subscription_id == subscription_id)
        .order_by(SecurityAppDevice.id.desc())
    )
    return result.scalars().all()


async def revoke_device(db: AsyncSession, device: SecurityAppDevice) -> SecurityAppDevice:
    if device.revoked_at is None:
        device.revoked_at = datetime.now(timezone.utc)
        device.push_token = None
        await db.commit()
        await db.refresh(device)
    return device
