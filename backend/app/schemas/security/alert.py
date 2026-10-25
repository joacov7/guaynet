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
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    operator_notes: Optional[str] = None
    confirmation_sent_at: Optional[datetime] = None
    confirmation_expires_at: Optional[datetime] = None


class SecurityAlertUpdate(BaseModel):
    status: SecurityAlertStatus
    operator_notes: Optional[str] = None


class AlertPanelItem(BaseModel):
    """Enriched alert for the operator monitoring panel."""
    id: int
    alert_type: SecurityAlertType
    status: SecurityAlertStatus
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    operator_notes: Optional[str] = None
    confirmation_sent_at: Optional[datetime] = None
    confirmation_expires_at: Optional[datetime] = None
    subscription_id: int
    beat_account_id: Optional[str] = None
    property_name: str
    property_address: str
    plan_name: str
    zone_number: Optional[int] = None
    zone_name: Optional[str] = None
