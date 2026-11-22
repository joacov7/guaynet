"""
Panel-wide helpers for the top bar: global search (Ctrl+K) and the "Pendientes"
bell. Open to any logged-in user; each result group is filtered by the user's
section permissions (Usuarios → Permisos), so nothing shows that the user could
not open anyway.

The bell is computed from the live state of the system (routers down, active
alarms, overdue invoices...), not from stored notifications: an item disappears
on its own once the problem is solved.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import _is_admin, effective_permissions, get_current_user, get_db

router = APIRouter()


async def _viewer(db: AsyncSession, user):
    """sees(section) for this user."""
    if _is_admin(user):
        return lambda *_sections: True
    perms = await effective_permissions(db, user)
    return lambda *sections: any(perms.get(s, (False, False))[0] for s in sections)


# ── Search ───────────────────────────────────────────────────────────────────

@router.get("/search")
async def search(
    q: str = Query(..., min_length=2, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.client import Client
    from app.models.router import MikrotikRouter
    from app.models.ticket import Ticket

    sees = await _viewer(db, current_user)
    term = q.strip()
    # % and _ are wildcards in LIKE: searched literally
    esc = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{esc.lower()}%"
    results = []

    if sees("clients"):
        full = func.lower(func.concat(Client.first_name, " ", Client.last_name))
        full_rev = func.lower(func.concat(Client.last_name, " ", Client.first_name))
        rows = (await db.execute(
            select(Client).where(or_(
                full.like(like, escape="\\"), full_rev.like(like, escape="\\"),
                Client.ip_address.like(f"%{esc}%", escape="\\"),
                func.lower(func.coalesce(Client.dni, "")).like(like, escape="\\"),
                func.lower(func.coalesce(Client.phone, "")).like(like, escape="\\"),
                func.lower(func.coalesce(Client.mac_address, "")).like(like, escape="\\"),
                func.lower(func.coalesce(Client.email, "")).like(like, escape="\\"),
                func.lower(func.coalesce(Client.address, "")).like(like, escape="\\"),
            )).order_by(Client.last_name, Client.first_name).limit(8)
        )).scalars().all()
        status_label = {"active": "Activo", "suspended": "Cortado", "cancelled": "Baja"}
        for c in rows:
            st = c.status.value if hasattr(c.status, "value") else c.status
            results.append({
                "type": "client", "id": c.id, "title": c.full_name,
                "subtitle": " · ".join(x for x in (c.ip_address, c.address, status_label.get(st, st)) if x),
                "url": f"/clients/{c.id}",
            })

    if sees("tickets"):
        conds = [func.lower(Ticket.title).like(like, escape="\\")]
        digits = term.lstrip("#")
        if digits.isdigit():
            conds.append(Ticket.id == int(digits))
        rows = (await db.execute(
            select(Ticket).where(or_(*conds)).order_by(Ticket.created_at.desc()).limit(5)
        )).scalars().all()
        for t in rows:
            results.append({
                "type": "ticket", "id": t.id, "title": f"#{t.id} {t.title}",
                "subtitle": t.created_at.strftime("%d/%m/%Y") if t.created_at else "",
                "url": f"/clients/{t.client_id}" if t.client_id and sees("clients") else "/tickets",
            })

    if sees("routers"):
        rows = (await db.execute(
            select(MikrotikRouter).where(or_(
                func.lower(MikrotikRouter.name).like(like, escape="\\"),
                func.lower(MikrotikRouter.host).like(like, escape="\\"),
                func.lower(func.coalesce(MikrotikRouter.location, "")).like(like, escape="\\"),
            )).order_by(MikrotikRouter.name).limit(5)
        )).scalars().all()
        for r in rows:
            results.append({
                "type": "router", "id": r.id, "title": r.name,
                "subtitle": " · ".join(x for x in (r.host, r.location) if x), "url": "/routers",
            })

    return results


# ── Bell ─────────────────────────────────────────────────────────────────────

@router.get("/attention")
async def attention(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """What needs someone's attention now, most serious first."""
    from app.models.alarm import Alarm, AlarmStatus
    from app.models.automation_log import AutomationLog
    from app.models.invoice import Invoice, InvoiceStatus
    from app.models.router import DeviceStatus, MikrotikRouter
    from app.models.security.alert import SecurityAlert, SecurityAlertStatus
    from app.models.ticket import Ticket, TicketStatus
    from app.models.work_order import WorkOrder, WorkOrderStatus

    sees = await _viewer(db, current_user)
    now = datetime.now(timezone.utc)
    items = []

    def add(key, severity, title, count, url, detail=None):
        if count:
            items.append({"key": key, "severity": severity, "title": title, "count": count, "url": url, "detail": detail})

    if sees("security_alerts"):
        n = (await db.execute(select(func.count()).select_from(SecurityAlert)
                              .where(SecurityAlert.status == SecurityAlertStatus.new))).scalar() or 0
        add("security_alerts", "critical", f"{n} alerta{'s' if n != 1 else ''} de seguridad sin atender", n, "/security/operator-panel")

    if sees("routers", "monitoring"):
        names = (await db.execute(select(MikrotikRouter.name)
                                  .where(MikrotikRouter.status == DeviceStatus.offline)
                                  .order_by(MikrotikRouter.name))).scalars().all()
        n = len(names)
        add("routers_offline", "critical", f"{n} router{'s' if n != 1 else ''} sin respuesta", n,
            "/routers" if sees("routers") else "/monitoring",
            ", ".join(names[:5]) + ("…" if n > 5 else ""))

    if sees("alarms"):
        n = (await db.execute(select(func.count()).select_from(Alarm)
                              .where(Alarm.status == AlarmStatus.active))).scalar() or 0
        add("alarms", "warning", f"{n} alarma{'s' if n != 1 else ''} de red activa{'s' if n != 1 else ''}", n, "/alarms")

    if sees("tickets"):
        open_states = [TicketStatus.open, TicketStatus.in_progress]
        n = (await db.execute(select(func.count()).select_from(Ticket).where(
            Ticket.status == TicketStatus.open, Ticket.assigned_to_id.is_(None)))).scalar() or 0
        add("tickets_unassigned", "warning", f"{n} ticket{'s' if n != 1 else ''} sin asignar", n, "/tickets")
        n = (await db.execute(select(func.count()).select_from(Ticket).where(
            Ticket.status.in_(open_states), Ticket.assigned_to_id == current_user.id))).scalar() or 0
        add("tickets_mine", "info", f"{n} ticket{'s' if n != 1 else ''} asignado{'s' if n != 1 else ''} a vos", n, "/tickets")

    if sees("work_orders"):
        n = (await db.execute(select(func.count()).select_from(WorkOrder).where(
            WorkOrder.status.in_([WorkOrderStatus.pending, WorkOrderStatus.in_progress]),
            WorkOrder.scheduled_date.is_not(None), WorkOrder.scheduled_date < now))).scalar() or 0
        add("work_orders_late", "warning", f"{n} orden{'es' if n != 1 else ''} de trabajo atrasada{'s' if n != 1 else ''}", n, "/work-orders")

    if sees("billing"):
        n, total = (await db.execute(select(func.count(), func.coalesce(func.sum(Invoice.amount), 0))
                                     .where(Invoice.status == InvoiceStatus.overdue))).one()
        add("invoices_overdue", "info", f"{n} factura{'s' if n != 1 else ''} vencida{'s' if n != 1 else ''}", n, "/billing",
            f"Total ${float(total):,.0f}".replace(",", "."))

    if _is_admin(current_user):
        rows = (await db.execute(select(AutomationLog.job).where(
            AutomationLog.status == "error", AutomationLog.created_at >= now - timedelta(hours=48)
        ))).scalars().all()
        add("jobs_failed", "warning", f"{len(rows)} tarea{'s' if len(rows) != 1 else ''} automática{'s' if len(rows) != 1 else ''} con error (48 h)",
            len(rows), "/automations", ", ".join(sorted(set(rows))))

    order = {"critical": 0, "warning": 1, "info": 2}
    items.sort(key=lambda i: order[i["severity"]])
    return {"items": items, "checked_at": now.isoformat()}
