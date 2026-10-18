"""
Billing automation tasks.
Run via Celery Beat on a schedule defined in celery_app.py.
"""
import asyncio
from datetime import date, timedelta

from app.tasks.celery_app import celery_app


def _run(coro):
    return asyncio.run(coro)


from app.services.telegram import send_telegram as _send_telegram


@celery_app.task(name="app.tasks.billing.mark_overdue_and_suspend")
def mark_overdue_and_suspend(grace_days: int = 3):
    """
    1. Mark pending invoices past due_date as overdue.
    2. Suspend clients whose oldest overdue invoice exceeds grace_days.
    3. Write audit log entries and send Telegram summary.
    """

    async def _execute():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.audit import AuditLog
        from app.models.client import Client, ClientStatus
        from app.models.invoice import Invoice, InvoiceStatus
        from app.models.router import MikrotikRouter
        from app.services.mikrotik import build_service_from_router, MikrotikError

        today = date.today()
        grace_cutoff = today - timedelta(days=grace_days)
        suspended_names = []
        overdue_count = 0

        async with AsyncSessionLocal() as db:
            # Step 1: mark overdue
            result = await db.execute(
                select(Invoice).where(
                    Invoice.status == InvoiceStatus.pending,
                    Invoice.due_date < today,
                )
            )
            for inv in result.scalars().all():
                inv.status = InvoiceStatus.overdue
                db.add(inv)
                overdue_count += 1
            await db.commit()

            # Step 2: suspend clients past grace period
            overdue_clients_r = await db.execute(
                select(Client.id)
                .join(Invoice, Invoice.client_id == Client.id)
                .where(
                    Invoice.status == InvoiceStatus.overdue,
                    Invoice.due_date <= grace_cutoff,
                    Client.status == ClientStatus.active,
                )
                .distinct()
            )
            client_ids = [row[0] for row in overdue_clients_r.all()]

            # Load WhatsApp config once
            from sqlalchemy import select as _select
            from app.models.config import SystemConfig
            wa_cfg: dict = {}
            for key in ("twilio_account_sid", "twilio_auth_token", "twilio_whatsapp_from", "whatsapp_reminder_template"):
                r = await db.execute(_select(SystemConfig).where(SystemConfig.key == key))
                rec = r.scalar_one_or_none()
                wa_cfg[key] = rec.value if rec else None

            for client_id in client_ids:
                client = await db.get(Client, client_id)
                if not client:
                    continue
                client.status = ClientStatus.suspended
                db.add(client)

                # Audit log entry
                db.add(AuditLog(
                    user_id=None,
                    username="sistema",
                    action="suspend",
                    entity_type="client",
                    entity_id=client.id,
                    entity_name=client.full_name,
                    details=f"Corte automático por falta de pago (gracia: {grace_days} días)",
                ))

                rt = await db.get(MikrotikRouter, client.router_id)
                if rt:
                    def _disable(router=rt, qname=client.mikrotik_queue_name):
                        svc = build_service_from_router(router)
                        with svc:
                            q = svc.get_queue_by_name(qname)
                            if q:
                                svc.disable_queue(q["id"])
                    try:
                        await asyncio.to_thread(_disable)
                    except MikrotikError:
                        pass

                suspended_names.append(client.full_name)

                # Send WhatsApp notification
                if client.phone and all(wa_cfg.get(k) for k in ("twilio_account_sid", "twilio_auth_token", "twilio_whatsapp_from")):
                    template = wa_cfg.get("whatsapp_reminder_template") or \
                        "Hola {nombre}, tu servicio fue suspendido por falta de pago. Comunicate con nosotros para regularizar."
                    # Find oldest overdue invoice amount
                    inv_r = await db.execute(
                        select(Invoice).where(
                            Invoice.client_id == client.id,
                            Invoice.status == InvoiceStatus.overdue,
                        ).order_by(Invoice.due_date)
                    )
                    oldest_inv = inv_r.scalars().first()
                    msg = template.format(
                        nombre=client.full_name,
                        monto=f"${oldest_inv.amount:,.2f}" if oldest_inv else "",
                        vencimiento=str(oldest_inv.due_date) if oldest_inv else "",
                    )
                    try:
                        from twilio.rest import Client as TwilioClient
                        def _send_wa(account_sid=wa_cfg["twilio_account_sid"],
                                     auth_token=wa_cfg["twilio_auth_token"],
                                     from_=wa_cfg["twilio_whatsapp_from"],
                                     phone=client.phone,
                                     body=msg):
                            tc = TwilioClient(account_sid, auth_token)
                            to = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
                            tc.messages.create(from_=from_, to=to, body=body)
                        await asyncio.to_thread(_send_wa)
                    except Exception:
                        pass

            await db.commit()

        if suspended_names:
            names_list = "\n".join(f"  • {n}" for n in suspended_names)
            await _send_telegram(
                f"⚠️ Corte automático por falta de pago\n"
                f"{len(suspended_names)} cliente(s) suspendidos:\n{names_list}"
            )

        return {"overdue_marked": overdue_count, "clients_suspended": len(suspended_names)}

    return _run(_execute())


@celery_app.task(name="app.tasks.billing.generate_monthly_invoices")
def generate_monthly_invoices():
    """Generate a pending invoice for every active client for the current month."""

    async def _execute():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.client import Client, ClientStatus
        from app.models.invoice import Invoice, InvoiceStatus
        from app.models.plan import Plan

        today = date.today()
        period = today.strftime("%Y-%m")
        created = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Client).where(Client.status == ClientStatus.active))
            clients = result.scalars().all()

            for client in clients:
                existing = await db.execute(
                    select(Invoice).where(
                        Invoice.client_id == client.id,
                        Invoice.period == period,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                plan = await db.get(Plan, client.plan_id)
                if not plan:
                    continue

                billing_day = min(client.billing_day, 28)
                due_date = date(today.year, today.month, billing_day)
                if due_date < today:
                    if today.month == 12:
                        due_date = date(today.year + 1, 1, billing_day)
                    else:
                        due_date = date(today.year, today.month + 1, billing_day)

                invoice = Invoice(
                    client_id=client.id,
                    period=period,
                    amount=plan.price,
                    issue_date=today,
                    due_date=due_date,
                    status=InvoiceStatus.pending,
                )
                db.add(invoice)
                created += 1

            await db.commit()

        return {"invoices_created": created, "period": period}

    return _run(_execute())
