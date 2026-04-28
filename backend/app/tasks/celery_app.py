from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "guaynet",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.billing"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Argentina/Buenos_Aires",
    enable_utc=True,
    beat_schedule={
        "mark-overdue-daily": {
            "task": "app.tasks.billing.mark_overdue_and_suspend",
            "schedule": crontab(hour=8, minute=0),
        },
        "generate-monthly-invoices": {
            "task": "app.tasks.billing.generate_monthly_invoices",
            "schedule": crontab(hour=9, minute=0, day_of_month=1),
        },
    },
)
