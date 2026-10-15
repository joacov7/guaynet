from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.router import DeviceStatus, MikrotikRouter
from app.schemas.dashboard import DashboardStats, RouterStatusItem

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    today = date.today()
    this_month = today.strftime("%Y-%m")
    last_month_date = date(today.year, today.month - 1, 1) if today.month > 1 else date(today.year - 1, 12, 1)
    last_month = last_month_date.strftime("%Y-%m")

    # ── Clients ───────────────────────────────────────────────────────────────
    async def count_clients(status: ClientStatus) -> int:
        r = await db.execute(select(func.count()).where(Client.status == status))
        return r.scalar_one()

    total_r = await db.execute(select(func.count()).select_from(Client))
    total_clients = total_r.scalar_one()
    active_clients = await count_clients(ClientStatus.active)
    suspended_clients = await count_clients(ClientStatus.suspended)
    cancelled_clients = await count_clients(ClientStatus.cancelled)

    # ── Invoices ──────────────────────────────────────────────────────────────
    pending_r = await db.execute(select(func.count()).where(Invoice.status == InvoiceStatus.pending))
    overdue_r = await db.execute(select(func.count()).where(Invoice.status == InvoiceStatus.overdue))

    revenue_this_r = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.status == InvoiceStatus.paid, Invoice.period == this_month
        )
    )
    revenue_last_r = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.status == InvoiceStatus.paid, Invoice.period == last_month
        )
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    routers_r = await db.execute(select(MikrotikRouter).order_by(MikrotikRouter.name))
    routers = routers_r.scalars().all()

    router_statuses = []
    for rt in routers:
        c_r = await db.execute(select(func.count()).where(Client.router_id == rt.id))
        router_statuses.append(
            RouterStatusItem(
                id=rt.id,
                name=rt.name,
                location=rt.location,
                status=rt.status.value,
                client_count=c_r.scalar_one(),
            )
        )

    return DashboardStats(
        total_clients=total_clients,
        active_clients=active_clients,
        suspended_clients=suspended_clients,
        cancelled_clients=cancelled_clients,
        invoices_pending=pending_r.scalar_one(),
        invoices_overdue=overdue_r.scalar_one(),
        revenue_this_month=float(revenue_this_r.scalar_one()),
        revenue_last_month=float(revenue_last_r.scalar_one()),
        total_routers=len(routers),
        routers_online=sum(1 for r in routers if r.status == DeviceStatus.online),
        routers_offline=sum(1 for r in routers if r.status == DeviceStatus.offline),
        router_statuses=router_statuses,
    )
