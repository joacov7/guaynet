from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "guaynet",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.billing", "app.tasks.monitoring", "app.tasks.security"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Argentina/Buenos_Aires",
    enable_utc=True,

    # ── Queue definitions ──────────────────────────────────────────────────────
    # critical: security alerts, panic, entry timeout, duress — highest priority
    # default:  network monitoring, bandwidth sampling
    # low:      billing, report generation, non-urgent notifications
    task_queues={
        "critical": {"exchange": "critical", "routing_key": "critical"},
        "default":  {"exchange": "default",  "routing_key": "default"},
        "low":      {"exchange": "low",       "routing_key": "low"},
    },
    task_default_queue="default",
    task_routes={
        "app.tasks.security.*": {"queue": "critical"},
        "app.tasks.billing.*":  {"queue": "low"},
        "app.tasks.monitoring.*": {"queue": "default"},
    },

    beat_schedule={
        # ── Billing (low priority) ─────────────────────────────────────────────
        "mark-overdue-daily": {
            "task": "app.tasks.billing.mark_overdue_and_suspend",
            "schedule": crontab(hour=8, minute=0),
            "options": {"queue": "low"},
        },
        "generate-monthly-invoices": {
            "task": "app.tasks.billing.generate_monthly_invoices",
            "schedule": crontab(hour=9, minute=0, day_of_month=1),
            "options": {"queue": "low"},
        },
        # ── Network monitoring (default priority) ──────────────────────────────
        "check-routers-health": {
            "task": "app.tasks.monitoring.check_routers_health",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "default"},
        },
        "check-ubiquiti-health": {
            "task": "app.tasks.monitoring.check_ubiquiti_health",
            "schedule": crontab(minute="*/10"),
            "options": {"queue": "default"},
        },
        "collect-bandwidth-samples": {
            "task": "app.tasks.monitoring.collect_bandwidth_samples",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "default"},
        },
        "sample-wan-bytes": {
            "task": "app.tasks.monitoring.sample_wan_bytes",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "default"},
        },
        "reset-wan-counters": {
            "task": "app.tasks.monitoring.reset_wan_counters",
            "schedule": crontab(hour=0, minute=5, day_of_month=1),
            "options": {"queue": "default"},
        },
        # ── Security (critical priority) ────────────────────────────────────────
        "process-expired-entry-sessions": {
            "task": "app.tasks.security.process_expired_entry_sessions",
            "schedule": crontab(minute="*/1"),  # every minute
            "options": {"queue": "critical"},
        },
        "check-confirmation-timeouts": {
            "task": "app.tasks.security.check_confirmation_timeouts",
            "schedule": crontab(minute="*/1"),  # every minute
            "options": {"queue": "critical"},
        },
        "poll-beat-events": {
            "task": "app.tasks.security.poll_beat_events",
            "schedule": crontab(minute="*/2"),  # every 2 minutes while awaiting webhook support
            "options": {"queue": "critical"},
        },
        "generate-weekly-security-reports": {
            "task": "app.tasks.security.generate_weekly_reports",
            "schedule": crontab(hour=8, minute=0, day_of_week=1),  # every Monday 8am
            "options": {"queue": "low"},
        },
        "generate-monthly-security-reports": {
            "task": "app.tasks.security.generate_monthly_reports",
            "schedule": crontab(hour=3, minute=0, day_of_month=2),
            "options": {"queue": "low"},
        },
    },
)
