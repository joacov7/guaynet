from datetime import date, timedelta, timezone, datetime
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


@router.get("/oversubscription")
async def oversubscription_report(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Per-router oversubscription: sum of plan Mbps vs uplink capacity."""
    from app.models.plan import Plan
    from app.models.router import MikrotikRouter

    routers = (await db.execute(select(MikrotikRouter))).scalars().all()
    out = []
    for r in routers:
        dl_sum = await db.scalar(
            select(func.sum(Plan.download_mbps))
            .join(Client, Client.plan_id == Plan.id)
            .where(Client.router_id == r.id, Client.status == ClientStatus.active)
        ) or 0
        ul_sum = await db.scalar(
            select(func.sum(Plan.upload_mbps))
            .join(Client, Client.plan_id == Plan.id)
            .where(Client.router_id == r.id, Client.status == ClientStatus.active)
        ) or 0
        client_count = await db.scalar(
            select(func.count(Client.id)).where(
                Client.router_id == r.id, Client.status == ClientStatus.active
            )
        ) or 0
        dl_ratio = round(dl_sum / r.uplink_download_mbps, 2) if r.uplink_download_mbps else None
        ul_ratio = round(ul_sum / r.uplink_upload_mbps, 2) if r.uplink_upload_mbps else None
        out.append({
            "router_id": r.id,
            "router_name": r.name,
            "location": r.location,
            "uplink_download_mbps": r.uplink_download_mbps,
            "uplink_upload_mbps": r.uplink_upload_mbps,
            "subscribed_download_mbps": int(dl_sum),
            "subscribed_upload_mbps": int(ul_sum),
            "active_clients": client_count,
            "oversubscription_dl": dl_ratio,
            "oversubscription_ul": ul_ratio,
        })
    out.sort(key=lambda x: (x["oversubscription_dl"] or 0), reverse=True)
    return out


@router.get("/upgrade-candidates")
async def upgrade_candidates(
    days: int = Query(default=30, ge=7, le=90),
    threshold_pct: float = Query(default=80.0, ge=50, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Clients whose peak bandwidth usage exceeds threshold_pct of their plan limit."""
    from app.models.bandwidth import BandwidthSample
    from app.models.plan import Plan

    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            BandwidthSample.client_id,
            func.max(BandwidthSample.download_bytes).label("max_dl"),
            func.max(BandwidthSample.upload_bytes).label("max_ul"),
        )
        .where(
            BandwidthSample.client_id.isnot(None),
            BandwidthSample.sampled_at >= since,
        )
        .group_by(BandwidthSample.client_id)
    )
    rows = result.all()

    # Build client_id -> plan mapping
    client_ids = [r.client_id for r in rows if r.client_id]
    if not client_ids:
        return []

    clients_res = await db.execute(
        select(Client, Plan)
        .join(Plan, Client.plan_id == Plan.id)
        .where(Client.id.in_(client_ids), Client.status == ClientStatus.active)
    )
    client_map = {c.id: (c, p) for c, p in clients_res.all()}

    out = []
    for r in rows:
        if r.client_id not in client_map:
            continue
        client, plan = client_map[r.client_id]
        dl_limit_bytes = plan.download_mbps * 125_000
        ul_limit_bytes = plan.upload_mbps * 125_000
        dl_pct = round(r.max_dl / dl_limit_bytes * 100, 1) if dl_limit_bytes else 0
        ul_pct = round(r.max_ul / ul_limit_bytes * 100, 1) if ul_limit_bytes else 0
        peak_pct = max(dl_pct, ul_pct)
        if peak_pct >= threshold_pct:
            out.append({
                "client_id": client.id,
                "client_name": client.full_name,
                "plan_name": plan.name,
                "plan_download_mbps": plan.download_mbps,
                "plan_upload_mbps": plan.upload_mbps,
                "peak_download_pct": dl_pct,
                "peak_upload_pct": ul_pct,
                "peak_pct": peak_pct,
            })
    out.sort(key=lambda x: x["peak_pct"], reverse=True)
    return out
