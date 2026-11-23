"""
Billing rules shared by the panel, payments (manual and MercadoPago), the
scheduled jobs and the Telegram bot.
"""
import calendar
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.services.provisioning import ProvisionResult, provision_client

logger = logging.getLogger(__name__)


async def reactivate_if_settled(db: AsyncSession, client_id: int) -> ProvisionResult | None:
    """A suspended client with no overdue invoice left goes back to active and is
    unblocked on the router (also restores the plan speed after a throttle).
    Returns the router result, or None when nothing had to change."""
    client = await db.get(Client, client_id)
    if not client or client.status != ClientStatus.suspended:
        return None
    still_overdue = (await db.execute(
        select(Invoice.id).where(Invoice.client_id == client_id, Invoice.status == InvoiceStatus.overdue).limit(1)
    )).scalar_one_or_none()
    if still_overdue:
        return None

    client.status = ClientStatus.active
    await db.commit()
    result = await provision_client(db, client)
    if not result.ok:
        logger.warning("Client %s reactivated in Guaynet but not on the router: %s", client_id, result.message)
    try:
        from app.services.telegram import send_telegram
        await send_telegram(
            f"✅ Cliente reactivado automáticamente por pago: {client.full_name}"
            + ("" if result.ok else f"\n⚠️ {result.message}")
        )
    except Exception:
        pass
    return result


# ── Scheduled billing jobs (run by Celery beat or from the panel) ──────────────

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DEFAULT_SUSPENSION_TEXT = (
    "Hola {nombre}, tu servicio fue suspendido por falta de pago ({monto}). "
    "Comunicate con nosotros para regularizar."
)


def today_ar() -> date:
    """Business date in Argentina (the containers run in UTC: at 21:00 UTC it is already tomorrow)."""
    return datetime.now(AR_TZ).date()


async def _setting(db: AsyncSession, key: str, default: str = "") -> str:
    from app.models.config import SystemConfig
    row = await db.get(SystemConfig, key)
    return row.value if row and row.value is not None else default


async def log_job(db: AsyncSession, job: str, status: str, message: str, affected: int = 0) -> None:
    from app.models.automation_log import AutomationLog
    db.add(AutomationLog(job=job, status=status, message=message[:2000], affected=affected))
    await db.commit()


def _fill(template: str, **values: str) -> str:
    """{nombre}/{monto}/{vencimiento} placeholders; other braces are left alone (no str.format)."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


async def mark_overdue(db: AsyncSession, today: date | None = None) -> int:
    today = today or today_ar()
    invoices = (await db.execute(
        select(Invoice).where(Invoice.status == InvoiceStatus.pending, Invoice.due_date < today)
    )).scalars().all()
    for inv in invoices:
        inv.status = InvoiceStatus.overdue
    await db.commit()
    return len(invoices)


async def auto_suspend(db: AsyncSession, *, manual: bool = False, today: date | None = None) -> dict:
    """Mark overdue invoices, then suspend active clients whose overdue invoice is older
    than "Días de gracia" (Automatizaciones) and apply it on the routers.
    Scheduled runs do nothing while the switch is off; `manual` = a person pressed the button."""
    from app.models.audit import AuditLog
    from app.services.provisioning import provision_clients

    if not manual and await _setting(db, "auto_suspend_enabled", "false") != "true":
        return {"skipped": "corte automático desactivado"}
    today = today or today_ar()
    try:
        grace = max(0, min(365, int(await _setting(db, "auto_suspend_days", "30"))))
    except ValueError:
        grace = 30
    overdue_marked = await mark_overdue(db, today)
    cutoff = today - timedelta(days=grace)

    ids = (await db.execute(
        select(Client.id)
        .join(Invoice, Invoice.client_id == Client.id)
        .where(
            Invoice.status == InvoiceStatus.overdue,
            Invoice.due_date <= cutoff,
            Client.status == ClientStatus.active,
        )
        .distinct()
    )).scalars().all()
    clients = (await db.execute(select(Client).where(Client.id.in_(ids)))).scalars().all() if ids else []
    for client in clients:
        client.status = ClientStatus.suspended
        db.add(AuditLog(
            user_id=None, username="sistema", action="suspend", entity_type="client",
            entity_id=client.id, entity_name=client.full_name,
            details=f"Corte automático por falta de pago ({grace} días de gracia)",
        ))
    await db.commit()

    results = await provision_clients(db, clients) if clients else {}
    failed = [c for c in clients if not results.get(c.id) or not results[c.id].ok]

    sent = await _notify_suspended(db, clients) if clients else 0

    if clients:
        try:
            from app.services.telegram import send_telegram
            lines = "\n".join(f"  • {c.full_name}" for c in clients[:50])
            warn = f"\n⚠️ {len(failed)} sin aplicar en el router (revisar y usar «Sincronizar»)" if failed else ""
            await send_telegram(f"⚠️ Corte por falta de pago\n{len(clients)} cliente(s):\n{lines}{warn}")
        except Exception:
            pass

    summary = {
        "overdue_marked": overdue_marked,
        "clients_suspended": len(clients),
        "router_failed": len(failed),
        "whatsapp_sent": sent,
        "grace_days": grace,
    }
    msg = (f"Vencidas: {overdue_marked}. Cortados: {len(clients)}"
           + (f" ({', '.join(c.full_name for c in clients[:20])})" if clients else "")
           + (f". Sin aplicar en router: {', '.join(c.full_name for c in failed[:20])}" if failed else ""))
    await log_job(db, "auto_suspend", "error" if failed else "success", msg, len(clients))
    return summary


async def _notify_suspended(db: AsyncSession, clients: list) -> int:
    template = (await _setting(db, "whatsapp_suspension_template")) or DEFAULT_SUSPENSION_TEXT
    sent = 0
    try:
        from app.api.v1.endpoints.notifications import _send_whatsapp
    except Exception:
        return 0
    for client in clients:
        if not client.phone:
            continue
        oldest = (await db.execute(
            select(Invoice).where(Invoice.client_id == client.id, Invoice.status == InvoiceStatus.overdue)
            .order_by(Invoice.due_date).limit(1)
        )).scalar_one_or_none()
        body = _fill(template, nombre=client.full_name,
                     monto=f"${float(oldest.amount):,.2f}" if oldest else "",
                     vencimiento=oldest.due_date.strftime("%d/%m/%Y") if oldest else "")
        try:
            await _send_whatsapp(client.phone, body, db)
            sent += 1
        except Exception as exc:
            logger.warning("Suspension WhatsApp to client %s failed: %s", client.id, exc)
    return sent


def _due_date(billing_day: int, today: date) -> date:
    """This month's billing day; if it already passed (a run in the middle of the
    month), the same day next month. Short months use their last day."""
    day = max(1, billing_day or 1)
    due = date(today.year, today.month, min(day, calendar.monthrange(today.year, today.month)[1]))
    if due < today:
        y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        due = date(y, m, min(day, calendar.monthrange(y, m)[1]))
    return due


async def generate_monthly_invoices(db: AsyncSession, *, manual: bool = False, today: date | None = None) -> dict:
    """One invoice per active client for the current period (never twice).
    Scheduled runs respect "Facturación automática"; `manual` = a person pressed the button."""
    from app.models.plan import Plan

    if not manual and await _setting(db, "auto_invoice_enabled", "false") != "true":
        return {"skipped": "facturación automática desactivada"}
    today = today or today_ar()
    period = today.strftime("%Y-%m")
    clients = (await db.execute(select(Client).where(Client.status == ClientStatus.active))).scalars().all()
    already = set((await db.execute(select(Invoice.client_id).where(Invoice.period == period))).scalars().all())
    plans = {p.id: p for p in (await db.execute(select(Plan))).scalars().all()}
    created = 0
    for client in clients:
        plan = plans.get(client.plan_id)
        if client.id in already or not plan:
            continue
        db.add(Invoice(
            client_id=client.id, period=period, amount=plan.price, status=InvoiceStatus.pending,
            issue_date=today, due_date=_due_date(client.billing_day, today),
        ))
        created += 1
    await db.flush()
    from app.services.account import apply_credits_for
    await apply_credits_for(db, [c.id for c in clients if c.id not in already and plans.get(c.plan_id)])
    await db.commit()
    await log_job(db, "auto_invoice", "success", f"Período {period}: {created} facturas generadas", created)
    return {"invoices_created": created, "period": period}


async def send_due_reminders(db: AsyncSession, *, manual: bool = False, today: date | None = None) -> dict:
    """WhatsApp reminder N days before due date ("Recordatorios" in Automatizaciones)."""
    if not manual and await _setting(db, "auto_whatsapp_enabled", "false") != "true":
        return {"skipped": "recordatorios desactivados"}
    from sqlalchemy.orm import selectinload
    try:
        days = int(await _setting(db, "whatsapp_reminder_days", "3"))
    except ValueError:
        days = 3
    target = (today or today_ar()) + timedelta(days=days)
    template = (await _setting(db, "whatsapp_reminder_template")) or (await _setting(db, "whatsapp_template")) \
        or "Hola {nombre}, tu factura de {monto} vence el {vencimiento}."
    invoices = (await db.execute(
        select(Invoice).options(selectinload(Invoice.client))
        .where(Invoice.due_date == target, Invoice.status == InvoiceStatus.pending)
    )).scalars().all()
    from app.api.v1.endpoints.notifications import _send_whatsapp
    sent = 0
    for inv in invoices:
        client = inv.client
        if not client or client.status != ClientStatus.active or not client.phone:
            continue
        try:
            await _send_whatsapp(client.phone, _fill(
                template, nombre=client.full_name, monto=f"${float(inv.amount):,.2f}",
                vencimiento=inv.due_date.strftime("%d/%m/%Y")), db)
            sent += 1
        except Exception as exc:
            logger.warning("Reminder WhatsApp for invoice %s failed: %s", inv.id, exc)
    await log_job(db, "whatsapp_reminder", "success", f"Enviados: {sent}", sent)
    return {"sent": sent}
