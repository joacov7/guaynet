from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.client import ClientStatus


class PlanBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    download_mbps: int
    upload_mbps: int
    price: float


class RouterBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    location: Optional[str]


class ZoneBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    color: str


class ClientBase(BaseModel):
    first_name: str
    last_name: str
    dni: Optional[str] = None
    cuit: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    ip_address: str
    mac_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    plan_id: int
    router_id: int
    ubiquiti_device_id: Optional[int] = None
    zone_id: Optional[int] = None
    pppoe_username: Optional[str] = None
    service_start_date: Optional[date] = None
    billing_day: int = 1


class ClientCreate(ClientBase):
    status: ClientStatus = ClientStatus.active
    pppoe_password: Optional[str] = None


class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dni: Optional[str] = None
    cuit: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    plan_id: Optional[int] = None
    router_id: Optional[int] = None
    ubiquiti_device_id: Optional[int] = None
    zone_id: Optional[int] = None
    pppoe_username: Optional[str] = None
    pppoe_password: Optional[str] = None
    status: Optional[ClientStatus] = None
    billing_day: Optional[int] = None


class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ClientStatus
    full_name: str
    mikrotik_queue_name: str
    pppoe_username: Optional[str] = None
    has_pppoe: bool = False
    plan: Optional[PlanBrief] = None
    router: Optional[RouterBrief] = None
    zone: Optional[ZoneBrief] = None
    created_at: datetime
    mikrotik_error: Optional[str] = None
    mikrotik_sync: Optional[str] = None


class ClientListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    ip_address: str
    phone: Optional[str]
    status: ClientStatus
    plan: Optional[PlanBrief] = None
    router: Optional[RouterBrief] = None
