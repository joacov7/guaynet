from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SecurityAppDevice(Base, TimestampMixin):
    """
    A phone linked to a subscription through the mobile app.
    Linked with the portal link + alarm PIN; afterwards it authenticates with
    its own secret, so it can be revoked without rotating the portal link.
    """
    __tablename__ = "sec_app_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), index=True
    )
    device_name: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(20), default="android")
    secret_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 of the device secret
    push_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
