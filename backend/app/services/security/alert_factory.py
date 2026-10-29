"""
Alert factory — creates SecurityAlert rows from various triggers.
Used by the entry session service (duress/timeout) and the Celery tasks.
All functions are async and accept an open db session.
"""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.alert import SecurityAlert, SecurityAlertType, SecurityAlertStatus
from app.models.security.entry_session import EntrySession


async def create_entry_timeout_alert(
    db: AsyncSession,
    session: EntrySession,
) -> SecurityAlert:
    """Create an ENTRY_TIMEOUT alert for an expired EntrySession."""
    now = datetime.now(timezone.utc)
    idempotency_key = f"entry_timeout:{session.id}"

    # Idempotent: skip if already exists
    from sqlalchemy import select
    existing = await db.execute(
        select(SecurityAlert).where(SecurityAlert.idempotency_key == idempotency_key)
    )
    if existing.scalar_one_or_none():
        return existing.scalar_one_or_none()

    alert = SecurityAlert(
        subscription_id=session.subscription_id,
        alert_type=SecurityAlertType.ENTRY_TIMEOUT,
        status=SecurityAlertStatus.new,
        triggered_at=now,
        idempotency_key=idempotency_key,
    )
    db.add(alert)
    await db.flush()

    from app.services.security.notifications import dispatch_alert
    await dispatch_alert(alert, db)

    return alert


async def create_duress_alert(
    db: AsyncSession,
    session: EntrySession,
) -> SecurityAlert:
    """Create a DURESS alert when a duress PIN is used to cancel an entry session."""
    now = datetime.now(timezone.utc)
    idempotency_key = f"duress:{session.id}"

    from sqlalchemy import select
    existing = await db.execute(
        select(SecurityAlert).where(SecurityAlert.idempotency_key == idempotency_key)
    )
    if existing.scalar_one_or_none():
        return existing.scalar_one_or_none()

    alert = SecurityAlert(
        subscription_id=session.subscription_id,
        alert_type=SecurityAlertType.DURESS,
        status=SecurityAlertStatus.new,
        triggered_at=now,
        idempotency_key=idempotency_key,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    from app.services.security.notifications import dispatch_alert
    await dispatch_alert(alert, db)

    return alert


async def create_panic_alert(
    db: AsyncSession,
    subscription_id: int,
    idempotency_key: str,
    notes: str,
) -> SecurityAlert:
    """PANIC raised by a person (Telegram bot); dispatched like any other alert."""
    from sqlalchemy import select
    existing = (await db.execute(
        select(SecurityAlert).where(SecurityAlert.idempotency_key == idempotency_key)
    )).scalar_one_or_none()
    if existing:
        return existing

    alert = SecurityAlert(
        subscription_id=subscription_id,
        alert_type=SecurityAlertType.PANIC,
        status=SecurityAlertStatus.new,
        triggered_at=datetime.now(timezone.utc),
        idempotency_key=idempotency_key,
        operator_notes=notes,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    from app.services.security.notifications import dispatch_alert
    await dispatch_alert(alert, db, skip_confirmation=True)
    await db.commit()
    return alert


async def create_alert_from_event(
    db: AsyncSession,
    subscription_id: int,
    alert_type: SecurityAlertType,
    source_event_id: int,
    idempotency_key: str,
) -> SecurityAlert:
    """Create a SecurityAlert from a raw SecurityEvent (e.g. intrusion, panic)."""
    from sqlalchemy import select
    existing = await db.execute(
        select(SecurityAlert).where(SecurityAlert.idempotency_key == idempotency_key)
    )
    if existing.scalar_one_or_none():
        return existing.scalar_one_or_none()

    alert = SecurityAlert(
        subscription_id=subscription_id,
        source_event_id=source_event_id,
        alert_type=alert_type,
        status=SecurityAlertStatus.new,
        triggered_at=datetime.now(timezone.utc),
        idempotency_key=idempotency_key,
    )
    db.add(alert)
    await db.flush()
    return alert
