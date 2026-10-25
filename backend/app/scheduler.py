"""
Background scheduler for automated WISP tasks.
Started/stopped via FastAPI lifespan.
"""
import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="America/Argentina/Buenos_Aires")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_setting(db, key: str, default: str = "") -> str:
    from sqlalchemy import select
    from app.models.config import SystemConfig
    row = (await db.execute(select(SystemConfig).where(SystemConfig.key == key))).scalar_one_or_none()
    return row.value if row else default


async def _log(db, job: str, status: str, message: str, affected: int = 0):
    from app.models.automation_log import AutomationLog
    db.add(AutomationLog(job=job, status=status, message=message, affected=affected))
    await db.commit()


# ---------------------------------------------------------------------------
# Job: auto-suspend overdue clients
# ---------------------------------------------------------------------------

async def run_auto_suspend():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.client import Client, ClientStatus
    from app.models.invoice import Invoice, InvoiceStatus

    async with AsyncSessionLocal() as db:
        try:
            if await _get_setting(db, "auto_suspend_enabled", "false") != "true":
                return
            grace = int(await _get_setting(db, "auto_suspend_days", "30"))
            cutoff = date.today() - timedelta(days=grace)

            # Find active clients with at least one overdue invoice past the cutoff
            from sqlalchemy.orm import selectinload
            clients = (await db.execute(
                select(Client)
                .where(Client.status == ClientStatus.active)
                .options(selectinload(Client.invoices))
            )).scalars().all()

            suspended = []
            for client in clients:
                overdue = [
                    inv for inv in client.invoices
                    if inv.status == InvoiceStatus.overdue and inv.due_date and inv.due_date <= cutoff
                ]
                if overdue:
                    client.status = ClientStatus.suspended
                    suspended.append(client.full_name)

            if suspended:
                await db.commit()

            await _log(db, "auto_suspend", "success",
                       f"Suspendidos: {', '.join(suspended)}" if suspended else "Sin cambios",
                       len(suspended))
        except Exception as exc:
            logger.exception("auto_suspend failed")
            await _log(db, "auto_suspend", "error", str(exc))


# ---------------------------------------------------------------------------
# Job: auto-generate monthly invoices
# ---------------------------------------------------------------------------

async def run_auto_invoice():
    import calendar
    from datetime import date
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.core.database import AsyncSessionLocal
    from app.models.client import Client, ClientStatus
    from app.models.invoice import Invoice, InvoiceStatus

    async with AsyncSessionLocal() as db:
        try:
            if await _get_setting(db, "auto_invoice_enabled", "false") != "true":
                return

            today = date.today()
            period = today.strftime("%Y-%m")
            year, month = today.year, today.month
            last_day = calendar.monthrange(year, month)[1]

            clients = (await db.execute(
                select(Client)
                .options(selectinload(Client.plan))
                .where(Client.status == ClientStatus.active)
            )).scalars().all()

            existing_ids = set((await db.execute(
                select(Invoice.client_id).where(Invoice.period == period)
            )).scalars().all())

            created = 0
            for c in clients:
                if c.id in existing_ids or not c.plan:
                    continue
                billing_day = min(c.billing_day or 1, last_day)
                db.add(Invoice(
                    client_id=c.id,
                    period=period,
                    amount=float(c.plan.price),
                    status=InvoiceStatus.pending,
                    issue_date=today,
                    due_date=date(year, month, billing_day),
                ))
                created += 1

            if created:
                await db.commit()
            await _log(db, "auto_invoice", "success", f"Facturas generadas: {created}", created)
        except Exception as exc:
            logger.exception("auto_invoice failed")
            await _log(db, "auto_invoice", "error", str(exc))


# ---------------------------------------------------------------------------
# Job: auto WhatsApp reminders
# ---------------------------------------------------------------------------

async def run_whatsapp_reminder():
    from datetime import date
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.core.database import AsyncSessionLocal
    from app.models.client import Client, ClientStatus
    from app.models.invoice import Invoice, InvoiceStatus

    async with AsyncSessionLocal() as db:
        try:
            if await _get_setting(db, "auto_whatsapp_enabled", "false") != "true":
                return

            days = int(await _get_setting(db, "whatsapp_reminder_days", "3"))
            target_date = date.today() + timedelta(days=days)
            template = await _get_setting(db, "whatsapp_template",
                                          "Hola {nombre}, tu factura de ${monto} vence el {vencimiento}.")

            invoices = (await db.execute(
                select(Invoice)
                .options(selectinload(Invoice.client))
                .where(
                    Invoice.due_date == target_date,
                    Invoice.status == InvoiceStatus.pending,
                )
            )).scalars().all()

            sent = 0
            for inv in invoices:
                client = inv.client
                if not client or client.status != ClientStatus.active:
                    continue
                phone = client.phone
                if not phone:
                    continue
                body = (template
                        .replace("{nombre}", client.full_name)
                        .replace("{monto}", f"{inv.amount:.2f}")
                        .replace("{vencimiento}", str(inv.due_date)))
                try:
                    from app.api.v1.endpoints.notifications import _send_whatsapp
                    await _send_whatsapp(phone, body, db)
                    sent += 1
                except Exception:
                    pass

            await _log(db, "whatsapp_reminder", "success", f"Enviados: {sent}", sent)
        except Exception as exc:
            logger.exception("whatsapp_reminder failed")
            await _log(db, "whatsapp_reminder", "error", str(exc))


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------

def start():
    scheduler.add_job(run_auto_suspend, CronTrigger(hour=3, minute=0), id="auto_suspend", replace_existing=True)
    scheduler.add_job(run_auto_invoice, CronTrigger(day=1, hour=1, minute=0), id="auto_invoice", replace_existing=True)
    scheduler.add_job(run_whatsapp_reminder, CronTrigger(hour=9, minute=0), id="whatsapp_reminder", replace_existing=True)
    scheduler.start()
    logger.info("Automation scheduler started")


def stop():
    scheduler.shutdown(wait=False)
    logger.info("Automation scheduler stopped")
