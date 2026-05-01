from fastapi import APIRouter

from app.api.v1.endpoints import auth, clients, dashboard, firewall, invoices, plans, routers

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])
api_router.include_router(routers.router, prefix="/routers", tags=["routers"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(firewall.router, prefix="/firewall", tags=["firewall"])
