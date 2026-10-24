"""
Security module Celery tasks.

1. process_expired_entry_sessions — every minute.
   Finds EntrySession rows with status=active and expires_at <= now.
   For each: atomically marks as expired, creates SecurityAlert(ENTRY_TIMEOUT).
   Uses SELECT FOR UPDATE SKIP LOCKED to prevent duplicate processing.

2. poll_beat_events — every 2 minutes.
   Polls BEAT adapter for all active subscriptions with a beat_account_id.
   Inserts new SecurityEvent rows using idempotency_key for deduplication.
   Generates SecurityAlerts for intrusion, panic, duress, communication_lost events.

3. generate_monthly_reports — day 2 of each month.
   Generates summary reports for the previous month's activity.
   Full PDF generation is a future enhancement (Etapa 3).
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(
    name="app.tasks.security.process_expired_entry_sessions",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def process_expired_entry_sessions(self):
    """
    Atomically expire active EntrySession rows past their expires_at.
    For each expired session, create a SecurityAlert(ENTRY_TIMEOUT).
    """
    async def _execute():
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.security.entry_session import EntrySession, EntrySessionStatus
        from app.services.security.alert_factory import create_entry_timeout_alert

        now = datetime.now(timezone.utc)
        expired_count = 0
        alerts_created = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(EntrySession).where(
                    EntrySession.status == EntrySessionStatus.active,
                    EntrySession.expires_at <= now,
                ).with_for_update(skip_locked=True)
            )
            sessions = result.scalars().all()

            for session in sessions:
                session.status = EntrySessionStatus.expired
                db.add(session)
                expired_count += 1

                try:
                    alert = await create_entry_timeout_alert(db, session)
                    if alert:
                        alerts_created += 1
                except Exception as exc:
                    logger.error(
                        "Failed to create ENTRY_TIMEOUT alert for session %d: %s",
                        session.id, exc,
                    )

            await db.commit()

        return {"expired": expired_count, "alerts_created": alerts_created}

    try:
        return _run(_execute())
    except Exception as exc:
        logger.error("process_expired_entry_sessions failed: %s", exc)
        raise self.retry(exc=exc)


# Event types that should generate a SecurityAlert
_ALERTABLE_EVENT_TYPES = {
    "intrusion", "panic", "duress", "tamper", "communication_lost",
}

# Map from SecurityEventType value to SecurityAlertType value
_EVENT_TO_ALERT_TYPE = {
    "intrusion":          "INTRUSION",
    "panic":              "PANIC",
    "duress":             "DURESS",
    "tamper":             "SYSTEM_FAULT",
    "communication_lost": "CONNECTION_LOST",
}


@celery_app.task(
    name="app.tasks.security.poll_beat_events",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def poll_beat_events(self):
    """
    Poll BEAT adapter for new events on all active subscriptions.
    Skips subscriptions with no beat_account_id.
    Deduplicates via idempotency_key before inserting SecurityEvent rows.
    Generates alerts for actionable event types.
    """
    async def _execute():
        from datetime import datetime, timezone
        from sqlalchemy import select
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.exc import IntegrityError
        from app.core.database import AsyncSessionLocal
        from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
        from app.models.security.event import SecurityEvent
        from app.models.security.alert import SecurityAlert, SecurityAlertType, SecurityAlertStatus
        from app.services.security import get_beat_adapter

        adapter = get_beat_adapter()
        new_events = 0
        new_alerts = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SecuritySubscription).where(
                    SecuritySubscription.status == SecuritySubscriptionStatus.active,
                    SecuritySubscription.beat_account_id.is_not(None),
                )
            )
            subscriptions = result.scalars().all()

        for sub in subscriptions:
            try:
                beat_events = await asyncio.to_thread(
                    adapter.get_recent_events, sub.beat_account_id, 20
                )
            except Exception as exc:
                logger.warning(
                    "BEAT poll failed for subscription %d (account %s): %s",
                    sub.id, sub.beat_account_id, exc,
                )
                continue

            async with AsyncSessionLocal() as db:
                for beat_evt in beat_events:
                    now = datetime.now(timezone.utc)
                    ikey = f"{sub.beat_account_id}:{beat_evt.event_type.value}:{beat_evt.occurred_at.isoformat()}"

                    # Skip already-processed events
                    existing = await db.execute(
                        select(SecurityEvent).where(SecurityEvent.idempotency_key == ikey)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    event = SecurityEvent(
                        subscription_id=sub.id,
                        event_type=beat_evt.event_type.value,
                        occurred_at=beat_evt.occurred_at,
                        received_at=now,
                        zone_number=beat_evt.zone,
                        partition=beat_evt.partition,
                        user_code=beat_evt.user_code,
                        description=beat_evt.description,
                        source="mock" if adapter.adapter_name == "mock" else "beat",
                        raw_data=beat_evt.raw,
                        processed=False,
                        idempotency_key=ikey,
                    )
                    db.add(event)
                    try:
                        await db.flush()
                        new_events += 1
                    except IntegrityError:
                        await db.rollback()
                        continue

                    # Generate alert for actionable event types
                    if beat_evt.event_type.value in _ALERTABLE_EVENT_TYPES:
                        alert_type_str = _EVENT_TO_ALERT_TYPE.get(beat_evt.event_type.value)
                        if alert_type_str:
                            alert_ikey = f"beat_alert:{ikey}"
                            alert_existing = await db.execute(
                                select(SecurityAlert).where(
                                    SecurityAlert.idempotency_key == alert_ikey
                                )
                            )
                            if not alert_existing.scalar_one_or_none():
                                alert = SecurityAlert(
                                    subscription_id=sub.id,
                                    source_event_id=event.id,
                                    alert_type=SecurityAlertType(alert_type_str),
                                    status=SecurityAlertStatus.new,
                                    triggered_at=now,
                                    idempotency_key=alert_ikey,
                                )
                                db.add(alert)
                                event.processed = True
                                new_alerts += 1

                await db.commit()

        return {
            "subscriptions_polled": len(subscriptions),
            "new_events": new_events,
            "new_alerts": new_alerts,
        }

    try:
        return _run(_execute())
    except Exception as exc:
        logger.error("poll_beat_events failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.security.generate_monthly_reports",
    bind=True,
    max_retries=1,
)
def generate_monthly_reports(self):
    """
    Generate monthly activity summaries for all active subscriptions.
    Runs on day 2 of each month for the previous month.
    PDF generation is a future enhancement.
    """
    async def _execute():
        from datetime import date, datetime, timezone
        from sqlalchemy import select, func
        from app.core.database import AsyncSessionLocal
        from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
        from app.models.security.event import SecurityEvent, SecurityEventType
        from app.models.security.alert import SecurityAlert
        from app.models.security.report import SecurityMonthlyReport, SecurityMonthlyReportStatus

        today = date.today()
        # Report is for the previous month
        if today.month == 1:
            report_year, report_month = today.year - 1, 12
        else:
            report_year, report_month = today.year, today.month - 1
        period = f"{report_year:04d}-{report_month:02d}"

        generated = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SecuritySubscription).where(
                    SecuritySubscription.status == SecuritySubscriptionStatus.active
                )
            )
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                # Skip if report already exists for this period
                existing = await db.execute(
                    select(SecurityMonthlyReport).where(
                        SecurityMonthlyReport.subscription_id == sub.id,
                        SecurityMonthlyReport.period == period,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Count events for the period
                from sqlalchemy import extract
                event_result = await db.execute(
                    select(func.count()).select_from(SecurityEvent).where(
                        SecurityEvent.subscription_id == sub.id,
                        extract("year", SecurityEvent.occurred_at) == report_year,
                        extract("month", SecurityEvent.occurred_at) == report_month,
                    )
                )
                event_count = event_result.scalar() or 0

                test_result = await db.execute(
                    select(func.count()).select_from(SecurityEvent).where(
                        SecurityEvent.subscription_id == sub.id,
                        SecurityEvent.event_type == SecurityEventType.test.value,
                        extract("year", SecurityEvent.occurred_at) == report_year,
                        extract("month", SecurityEvent.occurred_at) == report_month,
                    )
                )
                test_count = test_result.scalar() or 0

                alert_result = await db.execute(
                    select(func.count()).select_from(SecurityAlert).where(
                        SecurityAlert.subscription_id == sub.id,
                        extract("year", SecurityAlert.triggered_at) == report_year,
                        extract("month", SecurityAlert.triggered_at) == report_month,
                    )
                )
                alert_count = alert_result.scalar() or 0

                report = SecurityMonthlyReport(
                    subscription_id=sub.id,
                    period=period,
                    generated_at=datetime.now(timezone.utc),
                    status=SecurityMonthlyReportStatus.ready,
                    event_count=event_count,
                    alert_count=alert_count,
                    test_count=test_count,
                    visit_count=0,  # visit tracking is a future enhancement
                )
                db.add(report)
                generated += 1

            await db.commit()

        return {"period": period, "reports_generated": generated}

    try:
        return _run(_execute())
    except Exception as exc:
        logger.error("generate_monthly_reports failed: %s", exc)
        raise self.retry(exc=exc)
