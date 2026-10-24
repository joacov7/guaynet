from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.security.property import PropertyType


class PropertyBase(BaseModel):
    name: str
    address: str
    property_type: PropertyType = PropertyType.home
    notes: Optional[str] = None
    internet_client_id: Optional[int] = None


class PropertyCreate(PropertyBase):
    owner_user_id: int


class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    property_type: Optional[PropertyType] = None
    notes: Optional[str] = None


class PropertyResponse(PropertyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
