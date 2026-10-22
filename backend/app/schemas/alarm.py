from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.alarm import AlarmStatus, AlarmType


class AlarmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    router_id: int
    router_name: Optional[str] = None
    router_host: Optional[str] = None
    client_name: Optional[str] = None
    type: AlarmType
    status: AlarmStatus
    triggered_at: datetime
    resolved_at: Optional[datetime]
    details: Optional[dict]
    created_at: datetime
