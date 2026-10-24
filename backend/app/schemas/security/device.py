from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.security.device import SecurityDeviceType


class SecurityDeviceBase(BaseModel):
    device_type: SecurityDeviceType
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_location: Optional[str] = None
    notes: Optional[str] = None


class SecurityDeviceCreate(SecurityDeviceBase):
    subscription_id: int


class SecurityDeviceUpdate(BaseModel):
    device_type: Optional[SecurityDeviceType] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_location: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class SecurityDeviceResponse(SecurityDeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    is_active: bool
