from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, clients, dashboard, firewall, inventory, invoices, notifications, permissions, plans, reports, routers, tickets, ubiquiti, vpn

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
