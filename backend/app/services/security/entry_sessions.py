from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.entry_session import EntrySession, EntrySessionStatus
from app.models.security.subscription import SecuritySubscription, SecurityFeatureName
from app.models.security.pin import PinCredential, PinType
from app.core.security import verify_password
from app.schemas.security.entry_session import EntrySessionCreate


_MAX_DURATION_MINUTES = 240
_PIN_MAX_ATTEMPTS = 5
_PIN_LOCKOUT_MINUTES = 15


async def _assert_feature_enabled(db: AsyncSession, subscription_id: int) -> None:
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(SecuritySubscription)
        .options(selectinload(SecuritySubscription.features))
        .where(SecuritySubscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    if not sub.has_feature(SecurityFeatureName.entry_secure):
        raise HTTPException(
            status_code=403,
            detail="La funcionalidad Entrada Segura no está habilitada en esta suscripción",
        )


async def list_active_sessions(
    db: AsyncSession,
    subscription_id: Optional[int] = None,
) -> List[EntrySession]:
    q = select(EntrySession).where(EntrySession.status == EntrySessionStatus.active)
    if subscription_id is not None:
        q = q.where(EntrySession.subscription_id == subscription_id)
    result = await db.execute(q)
    return result.scalars().all()


async def start_entry_session(
    db: AsyncSession,
    body: EntrySessionCreate,
    activated_by_user_id: int,
) -> EntrySession:
    await _assert_feature_enabled(db, body.subscription_id)

    # Only one active session per subscription
    existing = await db.execute(
        select(EntrySession).where(
            EntrySession.subscription_id == body.subscription_id,
            EntrySession.status == EntrySessionStatus.active,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Ya hay una sesión de entrada activa para esta suscripción",
        )

    now = datetime.now(timezone.utc)
    session = EntrySession(
        subscription_id=body.subscription_id,
        activated_by_user_id=activated_by_user_id,
        duration_minutes=body.duration_minutes,
        created_at=now,
        expires_at=now + timedelta(minutes=body.duration_minutes),
        status=EntrySessionStatus.active,
        location_lat=body.location_lat,
        location_lon=body.location_lon,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def cancel_entry_session(
    db: AsyncSession,
    session_id: int,
    pin: str,
) -> EntrySession:
    """
    Cancel an active entry session. Requires PIN verification.
    Constant-time comparison prevents timing attacks.
    Duress PIN cancels the session silently but triggers an alert.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(EntrySession)
        .where(EntrySession.id == session_id)
        .with_for_update()
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    if session.status != EntrySessionStatus.active:
        raise HTTPException(
            status_code=409,
            detail=f"La sesión ya está en estado {session.status.value}",
        )

    # Load both PIN types for this subscription — always verify both to avoid timing differences
    pins_result = await db.execute(
        select(PinCredential).where(
            PinCredential.subscription_id == session.subscription_id
        )
    )
    pin_credentials = pins_result.scalars().all()

    if not pin_credentials:
        raise HTTPException(
            status_code=422,
            detail="No hay PINs configurados para esta suscripción",
        )

    # Brute-force check — check any locked normal PIN
    for cred in pin_credentials:
        if cred.pin_type == PinType.normal:
            if cred.locked_until and cred.locked_until > now:
                raise HTTPException(
                    status_code=429,
                    detail="PIN bloqueado temporalmente por demasiados intentos fallidos",
                )

    matched_type: Optional[PinType] = None
    matched_cred: Optional[PinCredential] = None
    for cred in pin_credentials:
        if verify_password(pin, cred.pin_hash):
            matched_cred = cred
            matched_type = cred.pin_type
            break

    # Reject expired temporary PINs after constant-time verify
    if matched_cred is not None and matched_type == PinType.temporary:
        if matched_cred.expires_at and matched_cred.expires_at <= now:
            matched_type = None
            matched_cred = None

    if matched_type is not None and matched_cred is not None:
        matched_cred.failed_attempts = 0
        matched_cred.locked_until = None

    if matched_type is None:
        # Increment failed attempts on normal PIN
        for cred in pin_credentials:
            if cred.pin_type == PinType.normal:
                cred.failed_attempts = (cred.failed_attempts or 0) + 1
                if cred.failed_attempts >= _PIN_MAX_ATTEMPTS:
                    cred.locked_until = now + timedelta(minutes=_PIN_LOCKOUT_MINUTES)
        await db.commit()
        raise HTTPException(status_code=401, detail="PIN incorrecto")

    session.status = EntrySessionStatus.cancelled
    session.cancelled_at = now
    if matched_type == PinType.duress:
        session.cancel_reason = "pin_duress"
    elif matched_type == PinType.temporary:
        session.cancel_reason = "pin_temporary"
    else:
        session.cancel_reason = "pin_normal"
    await db.commit()
    await db.refresh(session)

    if matched_type == PinType.duress:
        # Duress: silently trigger a DURESS alert — done asynchronously to not delay response
        from app.services.security.alert_factory import create_duress_alert
        await create_duress_alert(db, session)

    return session
