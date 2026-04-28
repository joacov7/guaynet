from typing import List
from pydantic import BaseModel


class RouterStatusItem(BaseModel):
    id: int
    name: str
    location: str | None
    status: str
    client_count: int


class DashboardStats(BaseModel):
    total_clients: int
    active_clients: int
    suspended_clients: int
    cancelled_clients: int

    invoices_pending: int
    invoices_overdue: int
    revenue_this_month: float
    revenue_last_month: float

    total_routers: int
    routers_online: int
    routers_offline: int

    router_statuses: List[RouterStatusItem] = []
