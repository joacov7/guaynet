from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityBeatWebhook(Base):
    """
    Raw notification received from BEAT's webhook, plus the full event fetched
    from BEAT's API. Capture mode: stored as-is, no alerts are generated yet.
    """
    __tablename__ = "sec_beat_webhooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    remote_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    payload: Mapped[Any] = mapped_column(JSON)
    event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_detail: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    # pending | ok | error | no_event_id
    fetch_status: Mapped[str] = mapped_column(String(20), default="pending")
    fetch_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
