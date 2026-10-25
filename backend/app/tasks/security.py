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
    from app.tasks._async import run_async
    return run_async(coro)


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


# Event types that always generate a SecurityAlert
_ALERTABLE_EVENT_TYPES = {
    "intrusion", "panic", "duress", "tamper", "communication_lost",
}

# Event types that generate a SecurityAlert only when vacation mode is active
_VACATION_ALERTABLE_EVENT_TYPES = {"zone_open"}

# Map from SecurityEventType value to SecurityAlertType value
_EVENT_TO_ALERT_TYPE = {
    "intrusion":          "INTRUSION",
    "panic":              "PANIC",
    "duress":             "DURESS",
    "tamper":             "SYSTEM_FAULT",
    "communication_lost": "CONNECTION_LOST",
    "zone_open":          "INTRUSION",  # elevated when vacation mode active
}

# Event types that trigger immediate power-state Telegram notifications
_POWER_EVENT_TYPES = {"power_failure", "power_restored"}


async def _notify_power_event(db, sub_id: int, event_type: str) -> None:
    """
    Send a real-time Telegram message when power_failure or power_restored
    is detected. Routes to client_telegram_id and/or operator channel based
    on the subscription plan, mirroring the dispatch_alert routing logic.
    """
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.security.subscription import SecuritySubscription
        from app.services.telegram import send_telegram, send_telegram_to

        result = await db.execute(
            select(SecuritySubscription)
            .options(selectinload(SecuritySubscription.plan))
            .where(SecuritySubscription.id == sub_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            return

        if event_type == "power_failure":
            client_msg = (
                "⚡ *Corte de luz detectado*\n"
                "Tu alarma está funcionando con batería de respaldo."
            )
            operator_msg = f"⚡ *Corte de luz* — Suscripción #{sub_id}"
        else:
            client_msg = (
                "✅ *Energía restaurada*\n"
                "Tu alarma volvió a funcionar con energía de red."
            )
            operator_msg = f"✅ *Energía restaurada* — Suscripción #{sub_id}"

        sent = False
        if sub.client_telegram_id:
            await send_telegram_to(sub.client_telegram_id, client_msg)
            sent = True

        if sub.plan and sub.plan.includes_monitoring:
            await send_telegram(operator_msg)
            sent = True

        if not sent:
            logger.warning(
                "Power event %s for sub #%s: no notification channel configured.",
                event_type, sub_id,
            )
    except Exception as exc:
        logger.warning("Power event notification failed for sub #%s: %s", sub_id, exc)


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
            from datetime import date as _date
            from app.models.security.contract import VacationMode

            result = await db.execute(
                select(SecuritySubscription).where(
                    SecuritySubscription.status == SecuritySubscriptionStatus.active,
                    SecuritySubscription.beat_account_id.is_not(None),
                )
            )
            subscriptions = result.scalars().all()

            # Preload subscription IDs with an active vacation mode today
            today = _date.today()
            vm_result = await db.execute(
                select(VacationMode.subscription_id).where(
                    VacationMode.active == True,
                    VacationMode.start_date <= today,
                    VacationMode.end_date >= today,
                )
            )
            vacation_sub_ids: set[int] = {row[0] for row in vm_result.all()}

            from app.services.security.schedule import disarm_violation, schedules_by_subscription
            schedules = await schedules_by_subscription(db, [s.id for s in subscriptions])

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

                    # Real-time power failure / restoration notification
                    if beat_evt.event_type.value in _POWER_EVENT_TYPES:
                        await _notify_power_event(db, sub.id, beat_evt.event_type.value)

                    # Commercial schedule: disarming outside opening hours
                    if beat_evt.event_type.value == "disarmed" and sub.id in schedules:
                        reason = disarm_violation(schedules[sub.id], beat_evt.occurred_at)
                        if reason:
                            alert = SecurityAlert(
                                subscription_id=sub.id,
                                source_event_id=event.id,
                                alert_type=SecurityAlertType.SCHEDULE_VIOLATION,
                                status=SecurityAlertStatus.new,
                                triggered_at=now,
                                idempotency_key=f"schedule_disarm:{ikey}",
                                operator_notes=reason,
                            )
                            db.add(alert)
                            event.processed = True
                            new_alerts += 1
                            await db.flush()
                            from app.services.security.notifications import dispatch_alert
                            await dispatch_alert(alert, db)

                    # Generate alert for actionable event types (including vacation-elevated ones)
                    in_vacation = sub.id in vacation_sub_ids
                    is_alertable = (
                        beat_evt.event_type.value in _ALERTABLE_EVENT_TYPES
                        or (in_vacation and beat_evt.event_type.value in _VACATION_ALERTABLE_EVENT_TYPES)
                    )
                    if is_alertable:
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
    Generate monthly activity PDF reports for active subscriptions with the
    monthly_report feature enabled.  Runs on day 2 of each month for the
    previous month.  Delivers each report via Telegram to client_telegram_id
    when set.
    """
    async def _execute():
        from datetime import date
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.core.database import AsyncSessionLocal
        from app.models.security.subscription import (
            SecuritySubscription, SecuritySubscriptionStatus, SecurityFeatureName,
        )
        from app.models.security.report import SecurityMonthlyReport
        from app.services.security.monthly_report import generate_and_deliver

        today = date.today()
        if today.month == 1:
            report_year, report_month = today.year - 1, 12
        else:
            report_year, report_month = today.year, today.month - 1
        period = f"{report_year:04d}-{report_month:02d}"

        generated = 0
        skipped = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SecuritySubscription)
                .options(
                    selectinload(SecuritySubscription.plan),
                    selectinload(SecuritySubscription.features),
                )
                .where(SecuritySubscription.status == SecuritySubscriptionStatus.active)
            )
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                if not sub.has_feature(SecurityFeatureName.monthly_report):
                    skipped += 1
                    continue

                # Idempotency: skip if already generated
                existing = await db.execute(
                    select(SecurityMonthlyReport).where(
                        SecurityMonthlyReport.subscription_id == sub.id,
                        SecurityMonthlyReport.period == period,
                        SecurityMonthlyReport.status == "ready",
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                try:
                    await generate_and_deliver(db, sub, period, report_year, report_month)
                    generated += 1
                except Exception as exc:
                    logger.error(
                        "Monthly report failed for subscription #%s period %s: %s",
                        sub.id, period, exc,
                    )

            await db.commit()

        return {"period": period, "reports_generated": generated, "skipped": skipped}

    try:
        return _run(_execute())
    except Exception as exc:
        logger.error("generate_monthly_reports failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.security.check_elderly_activity",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def check_elderly_activity(self):
    """
    Check-in de bienestar para adultos mayores.

    For each active subscription with elderly_care feature enabled:
    - If current Argentina time >= config.check_until AND
      no disarmed/armed event occurred today before check_until
      → dispatch a one-time INACTIVITY alert.

    Runs every 15 min. Idempotent via SecurityAlert.idempotency_key.
    """
    async def _execute():
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.core.database import AsyncSessionLocal
        from app.models.security.subscription import (
            SecuritySubscription, SecuritySubscriptionStatus, SecurityFeatureName,
        )
        from app.models.security.event import SecurityEvent
        from app.models.security.alert import SecurityAlert, SecurityAlertType, SecurityAlertStatus
        from app.models.security.elderly import SecurityElderlyConfig
        from app.models.security.property import Property
        from app.services.security.notifications import dispatch_alert

        # Argentina is UTC-3 (no DST)
        AR_TZ = timezone(timedelta(hours=-3))
        now_ar = datetime.now(AR_TZ)

        fired = 0

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
            if not sub.has_feature(SecurityFeatureName.elderly_care):
                continue

            async with AsyncSessionLocal() as db:
                config_result = await db.execute(
                    select(SecurityElderlyConfig).where(
                        SecurityElderlyConfig.subscription_id == sub.id,
                        SecurityElderlyConfig.enabled.is_(True),
                    )
                )
                config = config_result.scalar_one_or_none()
                if config is None:
                    continue

                # Parse check_until as today's datetime in Argentina
                try:
                    until_h, until_m = (int(x) for x in config.check_until.split(":"))
                except ValueError:
                    logger.warning("Invalid check_until for sub #%s: %s", sub.id, config.check_until)
                    continue

                check_until_dt = now_ar.replace(
                    hour=until_h, minute=until_m, second=0, microsecond=0
                )

                # Only fire after the check window has passed
                if now_ar < check_until_dt:
                    continue

                today_str = now_ar.strftime("%Y-%m-%d")
                ikey = f"elderly_inactivity:{sub.id}:{today_str}"

                # Idempotency: skip if already dispatched today
                existing = await db.execute(
                    select(SecurityAlert).where(SecurityAlert.idempotency_key == ikey)
                )
                if existing.scalar_one_or_none():
                    continue

                # Check if there was any disarmed event today before check_until
                try:
                    from_h, from_m = (int(x) for x in config.check_from.split(":"))
                except ValueError:
                    from_h, from_m = 0, 0

                today_start = now_ar.replace(hour=0, minute=0, second=0, microsecond=0)

                activity_result = await db.execute(
                    select(SecurityEvent).where(
                        SecurityEvent.subscription_id == sub.id,
                        SecurityEvent.event_type.in_(["disarmed", "armed"]),
                        SecurityEvent.occurred_at >= today_start,
                        SecurityEvent.occurred_at <= check_until_dt,
                    ).limit(1)
                )
                if activity_result.scalar_one_or_none() is not None:
                    # Activity detected — all good
                    continue

                # Load property name for the alert message
                prop_result = await db.execute(
                    select(Property.name).where(Property.id == sub.property_id)
                )
                prop_row = prop_result.first()
                property_name = prop_row[0] if prop_row else f"Propiedad #{sub.property_id}"

                alert = SecurityAlert(
                    subscription_id=sub.id,
                    alert_type=SecurityAlertType.INACTIVITY,
                    status=SecurityAlertStatus.new,
                    triggered_at=datetime.now(timezone.utc),
                    idempotency_key=ikey,
                    operator_notes=(
                        f"Sin actividad antes de las {config.check_until} — {property_name}"
                    ),
                )
                db.add(alert)
                await db.flush()

                # Notify family member if configured
                if config.notify_telegram_id:
                    try:
                        from app.services.telegram import send_telegram_to
                        msg = (
                            f"⚠️ *Sin actividad detectada*\n"
                            f"*Propiedad:* {property_name}\n"
                            f"La alarma no fue desactivada antes de las {config.check_until}.\n"
                            f"_Por favor verificá que todo esté bien._"
                        )
                        await send_telegram_to(config.notify_telegram_id, msg)
                    except Exception as exc:
                        logger.warning("Elderly notify telegram failed for sub #%s: %s", sub.id, exc)

                # Also route through standard dispatch (operator channel if monitoring plan)
                await dispatch_alert(alert, db)
                await db.commit()
                fired += 1
                logger.info("INACTIVITY alert dispatched for sub #%s (%s)", sub.id, today_str)

        return {"fired": fired}

    try:
        return _run(_execute())
    except Exception as exc:
        logger.error("check_elderly_activity failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.security.expire_vacation_modes",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def expire_vacation_modes(self):
    """
    Daily task: auto-deactivate VacationMode records whose end_date < today.
    Sends a Telegram notification to the client on expiry.
    """
    async def _execute():
        from datetime import date
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.security.contract import VacationMode
        from app.models.security.subscription import SecuritySubscription
        from app.services.telegram import send_telegram_to

        today = date.today()
        expired = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VacationMode).where(
                    VacationMode.active == True,
                    VacationMode.end_date < today,
                )
            )
            rows = result.scalars().all()

            for vm in rows:
                vm.active = False
                expired += 1

                try:
                    sub = await db.get(SecuritySubscription, vm.subscription_id)
                    if sub and sub.client_telegram_id:
                        await send_telegram_to(
                            sub.client_telegram_id,
                            "✅ *Modo ausencia finalizado*\n"
                            f"El período de ausencia configurado hasta el "
                            f"{vm.end_date.strftime('%d/%m/%Y')} finalizó.\n"
                            "El monitoreo volvió a su configuración normal.",
                        )
                except Exception as exc:
                    logger.warning(
                        "Vacation expiry notification failed for vm #%d: %s", vm.id, exc
                    )

            await db.commit()

        return {"expired": expired}

    try:
        return _run(_execute())
    except Exception as exc:
        logger.error("expire_vacation_modes failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.security.check_schedule_closing",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def check_schedule_closing(self):
    """
    Every 5 minutes: for subscriptions with schedule_alerts, raise one
    SCHEDULE_VIOLATION per day if the alarm is still disarmed after the
    closing time + tolerance. The arm state is the latest armed/disarmed event.
    Also tells the owner (Telegram only, no alert) once per day when the alarm
    is still armed after opening time + tolerance ("no abrió a horario").
    """
    async def _execute():
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.security.alert import SecurityAlert, SecurityAlertStatus, SecurityAlertType
        from app.models.security.event import SecurityEvent
        from app.models.security.subscription import SecuritySubscription, SecuritySubscriptionStatus
        from app.services.security.notifications import dispatch_alert
        from app.services.security.schedule import (
            AR_TZ, closing_deadline, opening_window, schedules_by_subscription,
        )
        from app.services.telegram import send_telegram_to

        now = datetime.now(timezone.utc)
        local_date = now.astimezone(AR_TZ).date()
        local_day = local_date.isoformat()
        fired = 0
        not_opened = 0

        async def _arm_state(db, sub_id):
            last = await db.execute(
                select(SecurityEvent.event_type)
                .where(
                    SecurityEvent.subscription_id == sub_id,
                    SecurityEvent.event_type.in_(["armed", "disarmed"]),
                )
                .order_by(SecurityEvent.occurred_at.desc())
                .limit(1)
            )
            state = last.scalar_one_or_none()
            return getattr(state, "value", state)

        async with AsyncSessionLocal() as db:
            active = await db.execute(
                select(SecuritySubscription.id).where(
                    SecuritySubscription.status == SecuritySubscriptionStatus.active
                )
            )
            schedules = await schedules_by_subscription(db, [r[0] for r in active.all()])

            for sub_id, days in schedules.items():
                window = opening_window(days, now)
                if window is not None:
                    day_row, open_deadline = window
                    if day_row.not_opened_notified_on != local_date and await _arm_state(db, sub_id) == "armed":
                        sub = await db.get(SecuritySubscription, sub_id)
                        if sub and sub.client_telegram_id:
                            try:
                                await send_telegram_to(
                                    sub.client_telegram_id,
                                    "🕘 *El local todavía no abrió*\n"
                                    f"La alarma sigue armada después del horario de apertura "
                                    f"({day_row.open_time.strftime('%H:%M')}).",
                                )
                                not_opened += 1
                            except Exception as exc:
                                logger.warning("Not-opened notice failed for sub #%s: %s", sub_id, exc)
                        day_row.not_opened_notified_on = local_date
                        await db.commit()
                    continue

                deadline = closing_deadline(days, now)
                if deadline is None or now < deadline:
                    continue

                ikey = f"schedule_not_closed:{sub_id}:{local_day}"
                exists = await db.execute(
                    select(SecurityAlert.id).where(SecurityAlert.idempotency_key == ikey)
                )
                if exists.scalar_one_or_none():
                    continue

                if await _arm_state(db, sub_id) != "disarmed":
                    continue

                alert = SecurityAlert(
                    subscription_id=sub_id,
                    alert_type=SecurityAlertType.SCHEDULE_VIOLATION,
                    status=SecurityAlertStatus.new,
                    triggered_at=now,
                    idempotency_key=ikey,
                    operator_notes=(
                        f"La alarma sigue desarmada después del cierre "
                        f"({deadline.strftime('%H:%M')} con tolerancia)"
                    ),
                )
                db.add(alert)
                await db.flush()
                await dispatch_alert(alert, db)
                await db.commit()
                fired += 1

        return {"fired": fired, "not_opened_notices": not_opened}

    try:
        return _run(_execute())
    except Exception as exc:
        logger.error("check_schedule_closing failed: %s", exc)
        raise self.retry(exc=exc)
