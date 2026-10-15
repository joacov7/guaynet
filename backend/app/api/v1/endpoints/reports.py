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
