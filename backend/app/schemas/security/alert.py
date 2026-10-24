from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.security.alert import SecurityAlertType, SecurityAlertStatus


class SecurityAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    alert_type: SecurityAlertType
    status: SecurityAlertStatus
    title: str
    detail: Optional[str] = None
    idempotency_key: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class SecurityAlertUpdate(BaseModel):
    status: SecurityAlertStatus
    resolution_notes: Optional[str] = None
