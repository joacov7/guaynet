from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.security.event import SecurityEventType


class SecurityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    event_type: SecurityEventType
    occurred_at: datetime
    received_at: datetime
    zone_number: Optional[int] = None
    partition: Optional[int] = None
    user_code: Optional[str] = None
    description: Optional[str] = None
    source: str
    processed: bool
    idempotency_key: Optional[str] = None
