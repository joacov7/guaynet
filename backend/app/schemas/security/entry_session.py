from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.security.entry_session import EntrySessionStatus


class EntrySessionCreate(BaseModel):
    subscription_id: int
    duration_minutes: int = 60
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None

    @field_validator("duration_minutes")
    @classmethod
    def duration_range(cls, v: int) -> int:
        if not 1 <= v <= 240:
            raise ValueError("duration_minutes must be between 1 and 240")
        return v


class EntrySessionCancel(BaseModel):
    pin: str


class EntrySessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    activated_by_user_id: Optional[int] = None
    duration_minutes: int
    status: EntrySessionStatus
    created_at: datetime
    expires_at: datetime
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
