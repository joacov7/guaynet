from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityTelegramLink(Base):
    """
    One-time code to link a Telegram chat with a subscription, via the bot
    deep link https://t.me/<bot>?start=<code>. member_id NULL = the titular
    (fills SecuritySubscription.client_telegram_id); otherwise that member.
    Only the SHA-256 of the code is stored.
    """
    __tablename__ = "sec_telegram_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sec_property_members.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_chat_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
