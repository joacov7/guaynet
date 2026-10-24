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
                                await db.flush()
                                from app.services.security.notifications import dispatch_alert
                                await dispatch_alert(alert, db)

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
    name="app.tasks.security.check_confirmation_timeouts",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def check_confirmation_timeouts(self):
    """
    Escalate alerts whose client confirmation window has expired without a response.
    Runs every minute alongside process_expired_entry_sessions.
    """
    async def _execute():
        from datetime import datetime, timezone
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.core.database import AsyncSessionLocal
        from app.models.security.alert import SecurityAlert, SecurityAlertStatus
        from app.models.security.subscription import SecuritySubscription
        from app.models.security.property import Property
        from app.services.security.notifications import dispatch_alert_operator

        now = datetime.now(timezone.utc)
        escalated = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SecurityAlert)
                .options(selectinload(SecurityAlert.confirmations))
                .where(
                    SecurityAlert.confirmation_expires_at.is_not(None),
                    SecurityAlert.confirmation_expires_at <= now,
                    SecurityAlert.status == SecurityAlertStatus.new,
                )
                .with_for_update(skip_locked=True)
            )
            alerts = result.scalars().all()

            for alert in alerts:
                if alert.confirmations:
                    # Already answered — clear confirmation fields and skip
                    alert.confirmation_expires_at = None
                    db.add(alert)
                    continue

                # Window expired, no response — check if the plan has monitoring
                sub_result = await db.execute(
                    select(SecuritySubscription)
                    .options(selectinload(SecuritySubscription.plan))
                    .where(SecuritySubscription.id == alert.subscription_id)
                )
                sub = sub_result.scalar_one_or_none()

                property_name = ""
                prop_result = await db.execute(
                    select(Property.name).where(
                        Property.id == sub.property_id
                    ) if sub else select(Property.name).where(False)
                )
                prop_row = prop_result.first()
                if prop_row:
                    property_name = prop_row[0]

                includes_monitoring = sub.plan.includes_monitoring if (sub and sub.plan) else True

                # Clear the pending confirmation window
                alert.confirmation_expires_at = None
                db.add(alert)

                if includes_monitoring:
                    try:
                        await dispatch_alert_operator(alert, property_name)
                        escalated += 1
                    except Exception as exc:
                        logger.error("Failed to escalate alert %d after timeout: %s", alert.id, exc)
                else:
                    logger.warning(
                        "Alert %d confirmation timed out but plan has no monitoring — no operator dispatch.",
                        alert.id,
                    )

            await db.commit()

        return {"escalated": escalated}

    try:
        return _run(_execute())
    except Exception as exc:
        logger.error("check_confirmation_timeouts failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.security.generate_weekly_reports",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_weekly_reports(self):
    """
    Generate and send weekly alarm status reports to clients every Monday at 8am.
    Only runs for active subscriptions with the weekly_report feature enabled.
    Reports battery warnings (pilas inalámbricas bajas) and weekly activity.
    Idempotent: skips if the report for this ISO week already exists.
    """
    async def _execute():
        from datetime import date, datetime, timezone, timedelta
        from sqlalchemy import select, func, extract
        from sqlalchemy.orm import selectinload
        from app.core.database import AsyncSessionLocal
        from app.models.security.subscription import (
            SecuritySubscription, SecuritySubscriptionStatus, SecurityFeatureName,
        )
        from app.models.security.event import SecurityEvent, SecurityEventType
        from app.models.security.alert import SecurityAlert
        from app.models.security.report import SecurityWeeklyReport
        from app.models.security.property import Property

        today = date.today()
        # ISO week: Monday = day 1. We report the just-completed week (Mon–Sun).
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        week_label = f"{monday.isocalendar()[0]}-W{monday.isocalendar()[1]:02d}"

        period_start = datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59, tzinfo=timezone.utc)

        sent = 0
        skipped = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SecuritySubscription)
                .options(
                    selectinload(SecuritySubscription.features),
                    selectinload(SecuritySubscription.plan),
                )
                .where(SecuritySubscription.status == SecuritySubscriptionStatus.active)
            )
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                if not sub.has_feature(SecurityFeatureName.weekly_report):
                    continue

                # Idempotency: skip if already sent this week
                existing = await db.execute(
                    select(SecurityWeeklyReport).where(
                        SecurityWeeklyReport.subscription_id == sub.id,
                        SecurityWeeklyReport.week_label == week_label,
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                # Resolve property name
                prop_result = await db.execute(
                    select(Property.name).where(Property.id == sub.property_id)
                )
                prop_row = prop_result.first()
                property_name = prop_row[0] if prop_row else f"Suscripción #{sub.id}"

                # ── Event counts ───────────────────────────────────────────────
                def _count_events(event_type=None):
                    q = select(func.count()).select_from(SecurityEvent).where(
                        SecurityEvent.subscription_id == sub.id,
                        SecurityEvent.occurred_at >= period_start,
                        SecurityEvent.occurred_at <= period_end,
                    )
                    if event_type:
                        q = q.where(SecurityEvent.event_type == event_type)
                    return q

                event_count    = (await db.execute(_count_events())).scalar() or 0
                armed_count    = (await db.execute(_count_events(SecurityEventType.armed.value))).scalar() or 0
                disarmed_count = (await db.execute(_count_events(SecurityEventType.disarmed.value))).scalar() or 0
                test_count     = (await db.execute(_count_events(SecurityEventType.test.value))).scalar() or 0

                alert_count = (await db.execute(
                    select(func.count()).select_from(SecurityAlert).where(
                        SecurityAlert.subscription_id == sub.id,
                        SecurityAlert.triggered_at >= period_start,
                        SecurityAlert.triggered_at <= period_end,
                    )
                )).scalar() or 0

                # ── Battery warnings ───────────────────────────────────────────
                # battery_low events that don't have a matching battery_restored
                # for the same zone within the same period.
                battery_low_result = await db.execute(
                    select(SecurityEvent).where(
                        SecurityEvent.subscription_id == sub.id,
                        SecurityEvent.event_type == SecurityEventType.battery_low.value,
                        SecurityEvent.occurred_at >= period_start,
                        SecurityEvent.occurred_at <= period_end,
                    ).order_by(SecurityEvent.occurred_at)
                )
                battery_low_events = battery_low_result.scalars().all()

                restored_zones = set()
                restored_result = await db.execute(
                    select(SecurityEvent.zone_number).where(
                        SecurityEvent.subscription_id == sub.id,
                        SecurityEvent.event_type == SecurityEventType.battery_restored.value,
                        SecurityEvent.occurred_at >= period_start,
                        SecurityEvent.occurred_at <= period_end,
                    )
                )
                for row in restored_result:
                    if row[0] is not None:
                        restored_zones.add(row[0])

                battery_warnings = []
                seen_zones = set()
                for ev in battery_low_events:
                    zone = ev.zone_number
                    if zone in restored_zones or zone in seen_zones:
                        continue
                    seen_zones.add(zone)
                    battery_warnings.append({
                        "zone_number": zone,
                        "description": ev.description or (f"Zona {zone}" if zone else "Zona desconocida"),
                    })

                # ── Power failures ─────────────────────────────────────────────
                pf_result = await db.execute(
                    select(SecurityEvent).where(
                        SecurityEvent.subscription_id == sub.id,
                        SecurityEvent.event_type == SecurityEventType.power_failure.value,
                        SecurityEvent.occurred_at >= period_start,
                        SecurityEvent.occurred_at <= period_end,
                    ).order_by(SecurityEvent.occurred_at)
                )
                pf_events = pf_result.scalars().all()

                pr_result = await db.execute(
                    select(SecurityEvent).where(
                        SecurityEvent.subscription_id == sub.id,
                        SecurityEvent.event_type == SecurityEventType.power_restored.value,
                        SecurityEvent.occurred_at >= period_start,
                        SecurityEvent.occurred_at <= period_end,
                    ).order_by(SecurityEvent.occurred_at)
                )
                pr_events = pr_result.scalars().all()

                power_failures = []
                for pf in pf_events:
                    # Find the first power_restored event after this failure
                    restored_at = next(
                        (pr.occurred_at for pr in pr_events if pr.occurred_at > pf.occurred_at),
                        None,
                    )
                    duration_minutes = (
                        int((restored_at - pf.occurred_at).total_seconds() // 60)
                        if restored_at else None
                    )
                    power_failures.append({
                        "occurred_at": pf.occurred_at.isoformat(),
                        "duration_minutes": duration_minutes,
                        "restored": restored_at is not None,
                    })

                # ── Build and send Telegram message ────────────────────────────
                def _fmt_duration(minutes):
                    if minutes is None:
                        return "duración desconocida"
                    if minutes < 60:
                        return f"{minutes} min"
                    h, m = divmod(minutes, 60)
                    return f"{h} hs {m} min" if m else f"{h} hs"

                now = datetime.now(timezone.utc)
                start_str = monday.strftime("%d/%m")
                end_str = sunday.strftime("%d/%m/%Y")

                lines = [
                    f"📊 *Reporte semanal de tu alarma*",
                    f"*{property_name}*  |  {start_str} – {end_str}",
                    "",
                    "━━━━━━━━━━━━━━━",
                ]

                if battery_warnings:
                    lines.append("🔋 *Baterías inalámbricas*")
                    for w in battery_warnings:
                        desc = w["description"]
                        zone = w["zone_number"]
                        label = f"Zona {zone} — {desc}" if zone else desc
                        lines.append(f"  ⚠️ {label}")
                    lines.append("")
                else:
                    lines.append("🔋 *Baterías:* ✅ Todas en buen estado")

                if power_failures:
                    lines.append(f"⚡ *Cortes de luz* ({len(power_failures)})")
                    for pf in power_failures:
                        dt = datetime.fromisoformat(pf["occurred_at"])
                        dt_local = dt.astimezone()
                        date_str = dt_local.strftime("%d/%m %H:%M")
                        dur = _fmt_duration(pf["duration_minutes"])
                        if pf["restored"]:
                            lines.append(f"  · {date_str} — {dur}")
                        else:
                            lines.append(f"  · {date_str} — sin energía al cierre del reporte")
                    lines.append("")
                else:
                    lines.append("⚡ *Energía eléctrica:* ✅ Sin cortes")

                lines += [
                    "━━━━━━━━━━━━━━━",
                    "📡 *Actividad de la semana*",
                    f"  Armados: {armed_count}  ·  Desarmados: {disarmed_count}",
                    f"  Alarmas: {alert_count}  ·  Pruebas: {test_count}",
                    f"  Eventos totales: {event_count}",
                    "",
                ]

                has_issues = battery_warnings or power_failures or alert_count > 0
                if not has_issues:
                    lines.append("✅ *Tu sistema funcionó correctamente esta semana.*")
                else:
                    callouts = []
                    if battery_warnings:
                        callouts.append("revisá las baterías")
                    if power_failures:
                        callouts.append("hubo cortes de luz")
                    if alert_count > 0:
                        callouts.append("hubo alertas")
                    lines.append(f"⚠️ *Esta semana:* {', '.join(callouts)}.")

                message = "\n".join(lines)
                telegram_sent = False

                try:
                    if sub.client_telegram_id:
                        from app.services.telegram import send_telegram_to
                        await send_telegram_to(sub.client_telegram_id, message)
                        telegram_sent = True
                    elif sub.plan and sub.plan.includes_monitoring:
                        from app.services.telegram import send_telegram
                        await send_telegram(message)
                        telegram_sent = True
                except Exception as exc:
                    logger.warning(
                        "Failed to send weekly report for subscription %d: %s", sub.id, exc
                    )

                # ── Save report record ─────────────────────────────────────────
                report = SecurityWeeklyReport(
                    subscription_id=sub.id,
                    week_label=week_label,
                    period_start=period_start,
                    period_end=period_end,
                    generated_at=now,
                    sent_at=now if telegram_sent else None,
                    event_count=event_count,
                    armed_count=armed_count,
                    disarmed_count=disarmed_count,
                    alert_count=alert_count,
                    test_count=test_count,
                    battery_warning_count=len(battery_warnings),
                    battery_warnings=battery_warnings or None,
                    power_failure_count=len(power_failures),
                    power_failures=power_failures or None,
                )
                db.add(report)
                sent += 1

            await db.commit()

        return {"week": week_label, "sent": sent, "skipped": skipped}

    try:
        return _run(_execute())
    except Exception as exc:
        logger.error("generate_weekly_reports failed: %s", exc)
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
