from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ZoneBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#1677ff"
    router_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    router_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ZoneResponse(ZoneBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_count: int = 0
    created_at: datetime
