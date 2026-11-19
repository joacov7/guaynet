from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.security.device import SecurityDeviceType


class DeviceZoneBase(BaseModel):
    zone_number: int = Field(ge=1, le=999)
    zone_name: Optional[str] = Field(default=None, max_length=100)
    zone_type: Optional[str] = Field(default=None, max_length=50)
    enabled: bool = True


class DeviceZoneResponse(DeviceZoneBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class SecurityDeviceBase(BaseModel):
    device_type: SecurityDeviceType
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    install_date: Optional[date] = None
    warranty_months: Optional[int] = None
    location_description: Optional[str] = None
    notes: Optional[str] = None


class SecurityDeviceCreate(SecurityDeviceBase):
    subscription_id: int


class SecurityDeviceUpdate(BaseModel):
    device_type: Optional[SecurityDeviceType] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    install_date: Optional[date] = None
    warranty_months: Optional[int] = None
    location_description: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class SecurityDeviceResponse(SecurityDeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    is_active: bool
    zones: List[DeviceZoneResponse] = []
