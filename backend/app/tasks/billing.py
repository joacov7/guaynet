"""
Billing automation tasks, run by Celery beat (celery_app.py) or from the panel.
The rules live in app/services/billing.py; these tasks only open a session.
This is the ONLY scheduler for billing: the old in-process APScheduler jobs were
removed because they ran the same work with different rules.
"""
from app.tasks.celery_app import celery_app


def _run(coro):
    from app.tasks._async import run_async
    return run_async(coro)


async def _with_db(fn, **kwargs):
    from app.core.database import AsyncSessionLocal
    from app.services import billing

    async with AsyncSessionLocal() as db:
        try:
            return await fn(db, **kwargs)
        except Exception as exc:
            await db.rollback()
            await billing.log_job(db, fn.__name__, "error", f"{type(exc).__name__}: {exc}")
            raise


@celery_app.task(name="app.tasks.billing.mark_overdue_and_suspend")
def mark_overdue_and_suspend(manual: bool = False):
    """Mark overdue invoices and suspend clients past the grace days (Automatizaciones).
    Scheduled runs do nothing while "Corte automático" is off."""
    from app.services.billing import auto_suspend
    return _run(_with_db(auto_suspend, manual=manual))


@celery_app.task(name="app.tasks.billing.generate_monthly_invoices")
def generate_monthly_invoices(manual: bool = False):
    from app.services.billing import generate_monthly_invoices as generate
    return _run(_with_db(generate, manual=manual))


@celery_app.task(name="app.tasks.billing.send_payment_reminders")
def send_payment_reminders(manual: bool = False):
    from app.services.billing import send_due_reminders
    return _run(_with_db(send_due_reminders, manual=manual))
