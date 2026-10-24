from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.security.entry_session import EntrySessionStatus


class EntrySessionCreate(BaseModel):
    subscription_id: int
    member_id: Optional[int] = None
    duration_minutes: int = 60
    notes: Optional[str] = None


class EntrySessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    member_id: Optional[int] = None
    status: EntrySessionStatus
    started_at: datetime
    expires_at: datetime
    cancelled_at: Optional[datetime] = None
    notes: Optional[str] = None
