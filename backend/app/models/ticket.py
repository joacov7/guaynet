import enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.user import User


class TicketStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class TicketPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TicketCategory(str, enum.Enum):
    connectivity = "connectivity"
    speed = "speed"
    billing = "billing"
    equipment = "equipment"
    installation = "installation"
    other = "other"


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[TicketStatus] = mapped_column(SAEnum(TicketStatus), default=TicketStatus.open, index=True)
    priority: Mapped[TicketPriority] = mapped_column(SAEnum(TicketPriority), default=TicketPriority.medium)
    category: Mapped[TicketCategory] = mapped_column(SAEnum(TicketCategory), default=TicketCategory.other)

    client: Mapped[Optional["Client"]] = relationship(foreign_keys=[client_id])
    assigned_to: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to_id])
    comments: Mapped[List["TicketComment"]] = relationship(back_populates="ticket", cascade="all, delete-orphan", order_by="TicketComment.created_at")


class TicketComment(Base, TimestampMixin):
    __tablename__ = "ticket_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text)

    ticket: Mapped["Ticket"] = relationship(back_populates="comments")
    author: Mapped[Optional["User"]] = relationship(foreign_keys=[author_id])
