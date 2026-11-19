from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SecurityElderlyConfig(Base, TimestampMixin):
    """
    Check-in de bienestar para adultos mayores.

    If the subscription's alarm is not disarmed (or armed + disarmed) before
    `check_until` on any given day, an INACTIVITY alert is dispatched to the
    family member's Telegram and/or the operator channel.

    check_from / check_until are "HH:MM" strings in Argentina local time (UTC-3).
    Example: check_from="07:00", check_until="10:00" means:
      "If by 10am the alarm hasn't been disarmed, something may be wrong."

    notify_telegram_id is the family member's Telegram chat_id — separate from
    the subscription's client_telegram_id (which may belong to the elderly person).
    """
    __tablename__ = "sec_elderly_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    # "HH:MM" in Argentina local time (UTC-3)
    check_from: Mapped[str] = mapped_column(String(5), default="07:00")
    check_until: Mapped[str] = mapped_column(String(5), default="10:00")
    # Family member Telegram chat_id to notify (optional)
    notify_telegram_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
