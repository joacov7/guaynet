from fastapi import APIRouter

from app.api.v1.endpoints import admin, alarms, auth, clients, dashboard, expenses, firewall, inventory, invoices, notifications, permissions, plans, portal, push, reports, routers, tickets, ubiquiti, vpn, wan, work_orders, zones
from app.api.v1.endpoints.security import (
    alerts as sec_alerts,
    certificates as sec_certificates,
    devices as sec_devices,
    elderly as sec_elderly,
    entry_sessions as sec_entry_sessions,
    events as sec_events,
    members as sec_members,
    pins as sec_pins,
    plans as sec_plans,
    properties as sec_properties,
    subscriptions as sec_subscriptions,
    vacation as sec_vacation,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])
api_router.include_router(routers.router, prefix="/routers", tags=["routers"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(firewall.router, prefix="/firewall", tags=["firewall"])
api_router.include_router(ubiquiti.router, prefix="/ubiquiti", tags=["ubiquiti"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["permissions"])
api_router.include_router(vpn.router, prefix="/vpn", tags=["vpn"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(push.router, prefix="/push", tags=["push"])
api_router.include_router(portal.router, prefix="/portal", tags=["portal"])
api_router.include_router(zones.router, prefix="/zones", tags=["zones"])
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work_orders"])
api_router.include_router(alarms.router, prefix="/alarms", tags=["alarms"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
api_router.include_router(wan.router, prefix="/routers", tags=["wan"])

# ── Guaynet Seguridad ─────────────────────────────────────────────────────────
api_router.include_router(sec_properties.router, prefix="/security/properties", tags=["security"])
api_router.include_router(sec_subscriptions.router, prefix="/security/subscriptions", tags=["security"])
api_router.include_router(sec_alerts.router, prefix="/security/alerts", tags=["security"])
api_router.include_router(sec_entry_sessions.router, prefix="/security/entry-sessions", tags=["security"])
api_router.include_router(sec_events.router, prefix="/security/events", tags=["security"])
api_router.include_router(sec_members.router, prefix="/security/members", tags=["security"])
api_router.include_router(sec_devices.router, prefix="/security/devices", tags=["security"])
api_router.include_router(sec_pins.router, prefix="/security/pins", tags=["security"])
api_router.include_router(sec_vacation.router, prefix="/security/vacation", tags=["security"])
api_router.include_router(sec_plans.router, prefix="/security/plans", tags=["security"])
api_router.include_router(sec_certificates.router, prefix="/security/subscriptions", tags=["security"])
api_router.include_router(sec_certificates.public_router, prefix="/security/certificates", tags=["security"])
api_router.include_router(sec_elderly.router, prefix="/security/subscriptions", tags=["security"])
