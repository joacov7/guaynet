from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.router import DeviceStatus, UbiquitiDeviceType


class RouterBase(BaseModel):
    name: str
    host: str
    port: int = 8728
    username: str
    location: Optional[str] = None
    notes: Optional[str] = None


class RouterCreate(RouterBase):
    password: str


class RouterUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class RouterResponse(RouterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: DeviceStatus
    last_seen: Optional[datetime]
    client_count: int = 0


class RouterStats(BaseModel):
    identity: str
    version: str
    uptime: str
    cpu_load: str
    free_memory: str
    total_memory: str
    board_name: str = ""


class MikrotikQueueItem(BaseModel):
    id: str
    name: str
    target: str
    max_limit: str
    burst_limit: Optional[str]
    disabled: bool
    comment: Optional[str]
    bytes: Optional[str]
    packets: Optional[str]


# Ubiquiti
class UbiquitiDeviceCreate(BaseModel):
    name: str
    host: str
    device_type: UbiquitiDeviceType
    username: Optional[str] = None
    password: Optional[str] = None
    mac_address: Optional[str] = None
    mikrotik_router_id: Optional[int] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class UbiquitiDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    device_type: UbiquitiDeviceType
    mac_address: Optional[str]
    mikrotik_router_id: Optional[int]
    location: Optional[str]
    status: DeviceStatus
    last_seen: Optional[datetime]
