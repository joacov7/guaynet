import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.security.subscription import SecuritySubscription
    from app.models.user import User


class EntrySessionStatus(str, enum.Enum):
    active = "active"       # Timer running
    cancelled = "cancelled" # PIN entered before expiry
    expired = "expired"     # Timer ran out — alert was generated


class EntrySession(Base):
    """
    Entrada Segura: a server-side countdown timer.

    When a client enters their property and knows they have N minutes
    before the alarm triggers, they activate a timer here.
    Cancellation requires PIN validation on the server.
    Expiry is processed by a Celery task regardless of app state.

    Critical invariants:
    - expires_at is set on the server, never trusted from the client.
    - Cancellation and expiry processing are atomic (SELECT FOR UPDATE).
    - An alert is created at expiry, not before.
    - Only one active session per subscription at a time (enforced at service layer).
    """
    __tablename__ = "sec_entry_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id"), index=True
    )
    activated_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[EntrySessionStatus] = mapped_column(
        SAEnum(EntrySessionStatus, native_enum=False),
        default=EntrySessionStatus.active,
        index=True,
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Location at activation time (with consent)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    subscription: Mapped["SecuritySubscription"] = relationship(
        "SecuritySubscription", lazy="select"
    )
    activated_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[activated_by_user_id], lazy="select"
    )
