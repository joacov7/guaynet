from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class SecurityContract(Base, TimestampMixin):
    """
    Digital acceptance record for the security service contract.

    Records WHEN the client accepted, from WHERE (IP + user-agent),
    and a hash of the contract document they accepted.
    This is an immutable audit record — never updated after creation.
    """
    __tablename__ = "sec_contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), index=True
    )
    accepted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    version: Mapped[str] = mapped_column(String(20))
    accepted_at: Mapped[str] = mapped_column(String(30))  # ISO datetime string, immutable
    acceptance_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    acceptance_user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # SHA-256 of the contract text at acceptance time
    document_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class VacationMode(Base, TimestampMixin):
    """
    Modo ausencia / viaje.
    Active period during which monitoring sensitivity may be elevated
    and/or notification routing changes.
    Server enforces start/end dates. Only one active period per subscription.
    """
    __tablename__ = "sec_vacation_modes"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), index=True
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
