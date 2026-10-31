from fastapi import APIRouter, Depends

from app.core.deps import require_admin, section_guard

from app.api.v1.endpoints import admin, alarms, auth, automations, clients, dashboard, expenses, firewall, inventory, invoices, mobile, notifications, payments, permissions, plans, portal, push, reports, routers, tickets, ubiquiti, vpn, wan, work_orders, zones
from app.api.v1.endpoints.security import (
    alerts as sec_alerts,
    beat as sec_beat,
    certificates as sec_certificates,
    contracts as sec_contracts,
    dashboard as sec_dashboard,
    devices as sec_devices,
    elderly as sec_elderly,
    entry_sessions as sec_entry_sessions,
    events as sec_events,
    members as sec_members,
    monthly_reports as sec_monthly_reports,
    neighborhood as sec_neighborhood,
    pins as sec_pins,
    plans as sec_plans,
    properties as sec_properties,
    schedule as sec_schedule,
    settings as sec_settings,
    subscriptions as sec_subscriptions,
    vacation as sec_vacation,
)

api_router = APIRouter()

# Permissions (Usuarios → Permisos) are enforced here per router with
# section_guard: GET needs "ver", any change needs "editar". Routers without a
# guard are public (auth, portal, mobile app, webhooks), admin-only per
# endpoint, or modules that still have no section of their own (login only).

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"], dependencies=[Depends(section_guard("clients", also_view=("billing", "monitoring", "security_properties", "security_subscriptions")))])
api_router.include_router(plans.router, prefix="/plans", tags=["plans"], dependencies=[Depends(section_guard("plans", also_view=("clients", "firewall")))])
api_router.include_router(routers.router, prefix="/routers", tags=["routers"], dependencies=[Depends(section_guard("routers", also_view=("clients", "monitoring", "firewall", "ubiquiti", "bandwidth", "map")))])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"], dependencies=[Depends(section_guard("billing"))])
api_router.include_router(firewall.router, prefix="/firewall", tags=["firewall"], dependencies=[Depends(section_guard("firewall"))])
api_router.include_router(ubiquiti.router, prefix="/ubiquiti", tags=["ubiquiti"], dependencies=[Depends(section_guard("ubiquiti", also_view=("clients",)))])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["permissions"])
api_router.include_router(vpn.router, prefix="/vpn", tags=["vpn"], dependencies=[Depends(require_admin)])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"], dependencies=[Depends(section_guard("billing"))])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(push.router, prefix="/push", tags=["push"])
api_router.include_router(portal.router, prefix="/portal", tags=["portal"])
api_router.include_router(automations.router, prefix="/automations", tags=["automations"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(zones.router, prefix="/zones", tags=["zones"])
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work_orders"])
api_router.include_router(alarms.router, prefix="/alarms", tags=["alarms"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
api_router.include_router(wan.router, prefix="/routers", tags=["wan"], dependencies=[Depends(section_guard("routers"))])

# ── Guaynet Seguridad ─────────────────────────────────────────────────────────
api_router.include_router(sec_dashboard.router, prefix="/security/dashboard", tags=["security"], dependencies=[Depends(section_guard("security_alerts"))])
api_router.include_router(sec_properties.router, prefix="/security/properties", tags=["security"], dependencies=[Depends(section_guard("security_properties", also_view=("security_subscriptions", "security_members")))])
api_router.include_router(sec_subscriptions.router, prefix="/security/subscriptions", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions", also_view=("security_events", "security_neighborhood", "security_properties", "security_alerts")))])
api_router.include_router(sec_alerts.router, prefix="/security/alerts", tags=["security"], dependencies=[Depends(section_guard("security_alerts"))])
api_router.include_router(sec_entry_sessions.router, prefix="/security/entry-sessions", tags=["security"], dependencies=[Depends(section_guard("security_entry_sessions"))])
api_router.include_router(sec_events.router, prefix="/security/events", tags=["security"], dependencies=[Depends(section_guard("security_events"))])
api_router.include_router(sec_members.router, prefix="/security/members", tags=["security"], dependencies=[Depends(section_guard("security_members"))])
api_router.include_router(sec_devices.router, prefix="/security/devices", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_pins.router, prefix="/security/pins", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_vacation.router, prefix="/security/vacation", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_plans.router, prefix="/security/plans", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_certificates.router, prefix="/security/subscriptions", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_certificates.public_router, prefix="/security/certificates", tags=["security"])
api_router.include_router(sec_elderly.router, prefix="/security/subscriptions", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_neighborhood.router, prefix="/security/neighborhood-groups", tags=["security"], dependencies=[Depends(section_guard("security_neighborhood"))])
api_router.include_router(sec_monthly_reports.router, prefix="/security/subscriptions", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_schedule.router, prefix="/security/subscriptions", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_contracts.router, prefix="/security/contracts", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_settings.router, prefix="/security/settings", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
api_router.include_router(sec_beat.router, prefix="/security/beat", tags=["security"])
api_router.include_router(mobile.router, prefix="/mobile", tags=["mobile"])
api_router.include_router(mobile.admin_router, prefix="/security", tags=["security"], dependencies=[Depends(section_guard("security_subscriptions"))])
