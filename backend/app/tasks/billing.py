"""
Billing automation tasks.
Run via Celery Beat on a schedule defined in celery_app.py.
"""
import asyncio
from datetime import date, timedelta

from app.tasks.celery_app import celery_app


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.billing.mark_overdue_and_suspend")
def mark_overdue_and_suspend(grace_days: int = 3):
    """
    1. Mark pending invoices past due_date as overdue.
    2. Suspend clients whose oldest overdue invoice exceeds grace_days.
    """

    async def _execute():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.client import Client, ClientStatus
        from app.models.invoice import Invoice, InvoiceStatus
        from app.models.router import MikrotikRouter
        from app.services.mikrotik import build_service_from_router, MikrotikError

        today = date.today()
        grace_cutoff = today - timedelta(days=grace_days)
        suspended_count = 0
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

            for client_id in client_ids:
                client = await db.get(Client, client_id)
                if not client:
                    continue
                client.status = ClientStatus.suspended
                db.add(client)

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
                suspended_count += 1

            await db.commit()

        return {"overdue_marked": overdue_count, "clients_suspended": suspended_count}

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

                # Clamp billing_day to 28 so it works in all months
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
