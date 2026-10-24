import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.security.subscription import SecuritySubscription


class SecurityEventType(str, enum.Enum):
    """Raw event types as reported by BEAT or simulated by the mock adapter."""
    armed = "armed"
    disarmed = "disarmed"
    intrusion = "intrusion"
    battery_low = "battery_low"
    battery_restored = "battery_restored"
    power_failure = "power_failure"
    power_restored = "power_restored"
    communication_lost = "communication_lost"
    communication_restored = "communication_restored"
    tamper = "tamper"
    tamper_restored = "tamper_restored"
    zone_open = "zone_open"
    zone_restore = "zone_restore"
    test = "test"
    panic = "panic"
    duress = "duress"
    other = "other"


class SecurityEvent(Base):
    """
    Raw event received from BEAT (or injected by the mock adapter / manually).
    These are immutable records — never modified after insertion.
    Processed alerts are created from events by the alert service.
    """
    __tablename__ = "sec_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id"), index=True
    )
    event_type: Mapped[SecurityEventType] = mapped_column(
        SAEnum(SecurityEventType, native_enum=False), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Panel-reported fields (may be None depending on BEAT capabilities)
    zone_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    partition: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Source: "beat" | "mock" | "manual"
    source: Mapped[str] = mapped_column(String(20), default="beat")
    # Raw payload from BEAT for audit purposes
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Whether an alert has been generated from this event
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    subscription: Mapped["SecuritySubscription"] = relationship(
        "SecuritySubscription", back_populates="events"
    )
