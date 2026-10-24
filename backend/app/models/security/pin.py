import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class PinType(str, enum.Enum):
    normal = "normal"       # Standard cancel PIN for Entrada Segura
    duress = "duress"       # Coercion PIN — triggers silent alert on use
    temporary = "temporary" # Time-limited PIN for technicians / visitors


class PinCredential(Base, TimestampMixin):
    """
    Stores a bcrypt hash of a PIN. Never stores the PIN in plain text.

    Security constraints:
    - pin_hash uses bcrypt, same as passwords.
    - Verification always happens server-side.
    - failed_attempts and locked_until provide brute-force protection.
    - Response time for duress and normal PINs must be indistinguishable
      at the API layer (handled in the service, not here).
    - Audit log is written on every verification attempt.
    """
    __tablename__ = "sec_pin_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), index=True
    )
    pin_type: Mapped[PinType] = mapped_column(SAEnum(PinType, native_enum=False))
    pin_hash: Mapped[str] = mapped_column(String(255))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Temporary PINs only
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class SafeWord(Base, TimestampMixin):
    """
    Palabra segura: a word the client says when receiving a phone call
    from the monitoring central to confirm they are OK.

    Stored as a bcrypt hash. Used only at service layer.
    The existence of this record means the feature is configured.
    """
    __tablename__ = "sec_safe_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), unique=True
    )
    word_hash: Mapped[str] = mapped_column(String(255))
