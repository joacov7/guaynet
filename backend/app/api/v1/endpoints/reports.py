from datetime import date
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus, Payment

router = APIRouter()


@router.get("/monthly-revenue")
async def monthly_revenue(
    months: int = Query(default=12, ge=1, le=36),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Revenue per month (paid invoices) for the last N months."""
    today = date.today()

    result = await db.execute(
        select(
            extract("year", Invoice.paid_date).label("year"),
            extract("month", Invoice.paid_date).label("month"),
            func.sum(Invoice.amount).label("revenue"),
            func.count().label("count"),
        )
        .where(Invoice.status == InvoiceStatus.paid, Invoice.paid_date.isnot(None))
        .group_by("year", "month")
        .order_by("year", "month")
    )
    rows = result.all()
    return [
        {
            "period": f"{int(r.year):04d}-{int(r.month):02d}",
            "revenue": float(r.revenue),
            "count": r.count,
        }
        for r in rows
    ]


@router.get("/invoice-status-breakdown")
async def invoice_status_breakdown(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Count and total amount of invoices by status."""
    result = await db.execute(
        select(
            Invoice.status,
            func.count().label("count"),
            func.sum(Invoice.amount).label("total"),
        )
        .group_by(Invoice.status)
    )
    rows = result.all()
    return [
        {
            "status": r.status.value,
            "count": r.count,
            "total": float(r.total or 0),
        }
        for r in rows
    ]


@router.get("/clients-by-plan")
async def clients_by_plan(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Active clients grouped by plan."""
    from app.models.plan import Plan

    result = await db.execute(
        select(Plan.name, func.count(Client.id).label("count"))
        .join(Client, Client.plan_id == Plan.id)
        .where(Client.status == ClientStatus.active)
        .group_by(Plan.name)
        .order_by(func.count(Client.id).desc())
    )
    rows = result.all()
    return [{"plan": r.name, "count": r.count} for r in rows]


@router.get("/payment-methods")
async def payment_methods(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Payments grouped by method."""
    result = await db.execute(
        select(Payment.method, func.count().label("count"), func.sum(Payment.amount).label("total"))
        .group_by(Payment.method)
    )
    rows = result.all()
    return [{"method": r.method.value, "count": r.count, "total": float(r.total or 0)} for r in rows]


@router.get("/arpu-by-plan")
async def arpu_by_plan(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Average Revenue Per User grouped by plan (paid invoices)."""
    from app.models.plan import Plan

    result = await db.execute(
        select(
            Plan.name.label("plan_name"),
            func.count(func.distinct(Client.id)).label("client_count"),
            func.sum(Invoice.amount).label("total_revenue"),
            func.avg(Invoice.amount).label("avg_invoice"),
        )
        .join(Client, Invoice.client_id == Client.id)
        .join(Plan, Client.plan_id == Plan.id)
        .where(Invoice.status == InvoiceStatus.paid)
        .group_by(Plan.name)
        .order_by(func.sum(Invoice.amount).desc())
    )
    rows = result.all()
    return [
        {
            "plan_name": r.plan_name,
            "client_count": r.client_count,
            "total_revenue": float(r.total_revenue or 0),
            "avg_invoice": float(r.avg_invoice or 0),
        }
        for r in rows
    ]


@router.get("/churn")
async def churn_report(
    months: int = Query(default=12, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Monthly churn: clients suspended/cancelled per month vs active base."""
    today = date.today()
    rows_out = []
    for i in range(months - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        period = f"{y:04d}-{m:02d}"
        susp = await db.scalar(
            select(func.count(Client.id)).where(
                Client.status == ClientStatus.suspended,
                extract("year", Client.updated_at) == y,
                extract("month", Client.updated_at) == m,
            )
        )
        canc = await db.scalar(
            select(func.count(Client.id)).where(
                Client.status == ClientStatus.cancelled,
                extract("year", Client.updated_at) == y,
                extract("month", Client.updated_at) == m,
            )
        )
        total_active = await db.scalar(
            select(func.count(Client.id)).where(Client.status == ClientStatus.active)
        )
        rows_out.append({
            "period": period,
            "suspended": susp or 0,
            "cancelled": canc or 0,
            "total_active": total_active or 0,
        })
    return rows_out


@router.get("/revenue-by-zone")
async def revenue_by_zone(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Paid invoice revenue grouped by client zone."""
    from app.models.zone import Zone

    result = await db.execute(
        select(
            Zone.name.label("zone_name"),
            Zone.color.label("color"),
            func.count(func.distinct(Client.id)).label("client_count"),
            func.sum(Invoice.amount).label("total_revenue"),
        )
        .join(Client, Client.zone_id == Zone.id)
        .join(Invoice, Invoice.client_id == Client.id)
        .where(Invoice.status == InvoiceStatus.paid)
        .group_by(Zone.name, Zone.color)
        .order_by(func.sum(Invoice.amount).desc())
    )
    rows = result.all()
    no_zone_rev = await db.scalar(
        select(func.sum(Invoice.amount))
        .join(Client, Invoice.client_id == Client.id)
        .where(Invoice.status == InvoiceStatus.paid, Client.zone_id.is_(None))
    )
    no_zone_count = await db.scalar(
        select(func.count(func.distinct(Client.id))).where(Client.zone_id.is_(None))
    )
    out = [
        {
            "zone_name": r.zone_name,
            "color": r.color,
            "client_count": r.client_count,
            "total_revenue": float(r.total_revenue or 0),
        }
        for r in rows
    ]
    if no_zone_rev:
        out.append({
            "zone_name": "Sin zona",
            "color": "#8c8c8c",
            "client_count": no_zone_count or 0,
            "total_revenue": float(no_zone_rev or 0),
        })
    return out
