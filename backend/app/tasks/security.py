"""
Security module Celery tasks.

Three tasks registered here:

1. process_expired_entry_sessions — runs every minute.
   Finds EntrySession rows with status=active and expires_at <= now.
   For each: atomically marks as expired, creates a SecurityAlert(ENTRY_TIMEOUT).
   Uses SELECT FOR UPDATE to prevent duplicate processing.

2. poll_beat_events — runs every 2 minutes.
   Polls BEAT for new events on all active subscriptions.
   Creates SecurityEvent rows and triggers alert generation if needed.
   Idempotent: uses event idempotency_key to skip already-processed events.

3. generate_monthly_reports — runs on day 2 of each month.
   Generates PDF reports for all active subscriptions for the previous month.

All tasks follow the same pattern:
- asyncio.run() wraps async DB logic.
- Errors are logged, never silently swallowed for critical tasks.
- Each task is idempotent and safe to retry.
"""

import asyncio

from app.tasks.celery_app import celery_app


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
    For each expired session, create a SecurityAlert of type ENTRY_TIMEOUT.
    Uses SELECT FOR UPDATE SKIP LOCKED to avoid double-processing.
    """
    async def _execute():
        # Implementation goes in Etapa 3.
        # Placeholder: scan and log only.
        from datetime import datetime, timezone
        from sqlalchemy import select, update
        from app.core.database import AsyncSessionLocal
        from app.models.security.entry_session import EntrySession, EntrySessionStatus

        now = datetime.now(timezone.utc)
        expired_count = 0

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
                # TODO (Etapa 3): create SecurityAlert(ENTRY_TIMEOUT) and trigger notifications
                expired_count += 1

            await db.commit()

        return {"expired": expired_count}

    try:
        return _run(_execute())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.security.poll_beat_events",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def poll_beat_events(self):
    """
    Poll BEAT for new events on all active subscriptions.
    Skips subscriptions with no beat_account_id.
    Marks SecurityEvent rows as processed=False for the alert service to pick up.
    """
    async def _execute():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
        from app.services.security import get_beat_adapter

        adapter = get_beat_adapter()
        new_events = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SecuritySubscription).where(
                    SecuritySubscription.status == SecuritySubscriptionStatus.active,
                    SecuritySubscription.beat_account_id.is_not(None),
                )
            )
            subscriptions = result.scalars().all()

        for sub in subscriptions:
            # TODO (Etapa 3): fetch events, deduplicate, insert SecurityEvent rows
            _ = await asyncio.to_thread(adapter.get_recent_events, sub.beat_account_id, 20)
            new_events += 0  # placeholder

        return {"subscriptions_polled": len(subscriptions), "new_events": new_events}

    try:
        return _run(_execute())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.security.generate_monthly_reports",
    bind=True,
    max_retries=1,
)
def generate_monthly_reports(self):
    """
    Generate PDF monthly reports for all active subscriptions.
    Runs on day 2 of each month for the previous month.
    """
    async def _execute():
        # Implementation goes in Etapa 3.
        return {"reports_generated": 0}

    try:
        return _run(_execute())
    except Exception as exc:
        raise self.retry(exc=exc)
