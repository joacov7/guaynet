import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.security.subscription import SecuritySubscription
    from app.models.security.event import SecurityEvent
    from app.models.security.member import PropertyMember
    from app.models.user import User


class SecurityAlertType(str, enum.Enum):
    """
    Operational alert types. Separate from raw SecurityEventType.
    PANIC, DURESS and ENTRY_TIMEOUT are generated internally.
    INTRUSION, CHECKIN_MISSED, etc. are generated from BEAT events.
    """
    PANIC = "PANIC"
    ENTRY_TIMEOUT = "ENTRY_TIMEOUT"
    DURESS = "DURESS"
    INTRUSION = "INTRUSION"
    CHECKIN_MISSED = "CHECKIN_MISSED"
    INACTIVITY = "INACTIVITY"
    SYSTEM_FAULT = "SYSTEM_FAULT"
    CONNECTION_LOST = "CONNECTION_LOST"
    SCHEDULE_VIOLATION = "SCHEDULE_VIOLATION"


class SecurityAlertStatus(str, enum.Enum):
    new = "new"                   # Just created, not seen by operator
    acknowledged = "acknowledged" # Operator saw it, handling
    resolved = "resolved"         # Handled and closed
    false_alarm = "false_alarm"   # Confirmed false alarm


class SecurityAlert(Base, TimestampMixin):
    """
    Operational alert generated from a SecurityEvent or internally (panic, entry timeout).
    An alert has a lifecycle: new → acknowledged → resolved/false_alarm.
    """
    __tablename__ = "sec_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id"), index=True
    )
    # The raw event that originated this alert (nullable for internally-generated alerts)
    source_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sec_events.id", ondelete="SET NULL"), nullable=True
    )
    alert_type: Mapped[SecurityAlertType] = mapped_column(
        SAEnum(SecurityAlertType, native_enum=False), index=True
    )
    status: Mapped[SecurityAlertStatus] = mapped_column(
        SAEnum(SecurityAlertStatus, native_enum=False),
        default=SecurityAlertStatus.new,
        index=True,
    )
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Operator who handled the alert
    operator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    operator_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Idempotency key to prevent duplicate alerts for the same event
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)

    # Client confirmation flow ("¿Estás bien?")
    confirmation_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_telegram_msg_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    subscription: Mapped["SecuritySubscription"] = relationship(
        "SecuritySubscription", back_populates="alerts"
    )
    source_event: Mapped[Optional["SecurityEvent"]] = relationship(
        "SecurityEvent", foreign_keys=[source_event_id], lazy="select"
    )
    operator: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[operator_id], lazy="select"
    )
    deliveries: Mapped[List["AlertDelivery"]] = relationship(
        "AlertDelivery", back_populates="alert", cascade="all, delete-orphan"
    )
    confirmations: Mapped[List["AlertConfirmation"]] = relationship(
        "AlertConfirmation", back_populates="alert", cascade="all, delete-orphan"
    )


class AlertDeliveryChannel(str, enum.Enum):
    sms = "sms"
    whatsapp = "whatsapp"
    telegram = "telegram"
    push = "push"
    call = "call"
    central = "central"    # Sent to BEAT monitoring central


class AlertDelivery(Base):
    """
    Tracks each notification attempt for an alert.
    Separates the fact that an alert occurred from whether it was delivered.
    """
    __tablename__ = "sec_alert_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("sec_alerts.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[AlertDeliveryChannel] = mapped_column(
        SAEnum(AlertDeliveryChannel, native_enum=False)
    )
    recipient: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/sent/delivered/failed
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(default=0)

    alert: Mapped["SecurityAlert"] = relationship("SecurityAlert", back_populates="deliveries")


class AlertConfirmationResponse(str, enum.Enum):
    safe = "safe"
    need_help = "need_help"
    false_alarm = "false_alarm"


class AlertConfirmation(Base):
    """
    Client or member response to an alert notification.
    'I am safe' / 'I need help' / 'false alarm'.
    """
    __tablename__ = "sec_alert_confirmations"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("sec_alerts.id", ondelete="CASCADE"), index=True
    )
    confirmed_by_member_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sec_property_members.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    response: Mapped[AlertConfirmationResponse] = mapped_column(
        SAEnum(AlertConfirmationResponse, native_enum=False)
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    alert: Mapped["SecurityAlert"] = relationship("SecurityAlert", back_populates="confirmations")
