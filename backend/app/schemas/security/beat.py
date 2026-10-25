from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class BeatAccountStatusResponse(BaseModel):
    account_id: str
    armed: Optional[bool] = None
    last_event_at: Optional[datetime] = None
    signal_ok: Optional[bool] = None
    battery_ok: Optional[bool] = None
    power_ok: Optional[bool] = None
    available: bool
    error_message: Optional[str] = None
    is_simulated: bool
