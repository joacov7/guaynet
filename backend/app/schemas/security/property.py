from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.security.property import PropertyType


class PropertyBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    property_type: PropertyType = PropertyType.home
    notes: Optional[str] = None
    internet_client_id: Optional[int] = None


class PropertyCreate(PropertyBase):
    # Defaults to the staff user creating it: security-only clients have no user account
    owner_user_id: Optional[int] = None


class PropertyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    address: Optional[str] = Field(default=None, min_length=1, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    property_type: Optional[PropertyType] = None
    notes: Optional[str] = None
    internet_client_id: Optional[int] = None


class PropertyResponse(PropertyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
