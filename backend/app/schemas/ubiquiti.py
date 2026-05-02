from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.models.router import DeviceStatus, UbiquitiDeviceType


class UbiquitiDeviceCreate(BaseModel):
    name: str
    host: str
    device_type: UbiquitiDeviceType
    username: Optional[str] = "ubnt"
    password: Optional[str] = None
    mac_address: Optional[str] = None
    mikrotik_router_id: Optional[int] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class UbiquitiDeviceUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    device_type: Optional[UbiquitiDeviceType] = None
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
    username: Optional[str]
    mac_address: Optional[str]
    mikrotik_router_id: Optional[int]
    location: Optional[str]
    notes: Optional[str]
    status: DeviceStatus
    last_seen: Optional[datetime]
    model_name: Optional[str]
    firmware_version: Optional[str]
    ssid: Optional[str]
    frequency_mhz: Optional[int]
    channel_width_mhz: Optional[int]
    signal_dbm: Optional[int]
    ccq: Optional[int]
    client_count: int = 0


# ── Live data schemas ─────────────────────────────────────────────────────────

class DeviceInfo(BaseModel):
    model: str = ""
    firmware: str = ""
    hostname: str = ""
    uptime_seconds: int = 0
    cpu_load: float = 0
    ram_used_pct: float = 0


class WirelessConfig(BaseModel):
    mode: str = ""
    ssid: str = ""
    frequency_mhz: Optional[int] = None
    channel_width_mhz: Optional[int] = None
    tx_power_dbm: Optional[int] = None
    security: str = ""


class WirelessUpdate(BaseModel):
    frequency_mhz: Optional[int] = None
    channel_width_mhz: Optional[int] = None
    tx_power_dbm: Optional[int] = None


class LinkInfo(BaseModel):
    remote_name: str = ""
    remote_mac: str = ""
    signal_dbm: Optional[int] = None
    noise_dbm: Optional[int] = None
    snr_db: Optional[int] = None
    ccq: Optional[int] = None
    rx_rate_mbps: Optional[float] = None
    tx_rate_mbps: Optional[float] = None
    distance_m: Optional[int] = None


class StationInfo(BaseModel):
    mac: str
    ip: str = ""
    name: str = ""
    signal_dbm: Optional[int] = None
    noise_dbm: Optional[int] = None
    ccq: Optional[int] = None
    rx_rate_mbps: Optional[float] = None
    tx_rate_mbps: Optional[float] = None
    uptime_seconds: Optional[int] = None


class SurveyScan(BaseModel):
    ssid: str = ""
    mac: str = ""
    frequency_mhz: Optional[int] = None
    channel_width_mhz: Optional[int] = None
    signal_dbm: Optional[int] = None
    security: str = ""


class FrequencyRecommendation(BaseModel):
    frequency_mhz: int
    network_count: int
    congestion_score: float
    recommendation: str
    networks: List[str] = []
