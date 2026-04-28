from typing import Optional
from pydantic import BaseModel, ConfigDict


class PlanBase(BaseModel):
    name: str
    description: Optional[str] = None
    download_mbps: int
    upload_mbps: int
    burst_download_mbps: Optional[int] = None
    burst_upload_mbps: Optional[int] = None
    burst_threshold_mbps: Optional[int] = None
    burst_time_seconds: int = 10
    price: float
    is_active: bool = True


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    download_mbps: Optional[int] = None
    upload_mbps: Optional[int] = None
    burst_download_mbps: Optional[int] = None
    burst_upload_mbps: Optional[int] = None
    burst_threshold_mbps: Optional[int] = None
    burst_time_seconds: Optional[int] = None
    price: Optional[float] = None
    is_active: Optional[bool] = None


class PlanResponse(PlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mikrotik_max_limit: str
    mikrotik_burst_limit: Optional[str]
    client_count: int = 0
