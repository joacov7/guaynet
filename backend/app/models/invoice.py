import enum
from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    transfer = "transfer"
    mercadopago = "mercadopago"
    other = "other"


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    # Billing period e.g. "2024-01"
    period: Mapped[str] = mapped_column(String(7))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    paid_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(SAEnum(InvoiceStatus), default=InvoiceStatus.pending)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # AFIP (Argentina electronic invoicing)
    afip_cae: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    afip_cae_expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    invoice_type: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    invoice_point_of_sale: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    invoice_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="invoices")
    payments: Mapped[List["Payment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    payment_date: Mapped[date] = mapped_column(Date)
    method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod))
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
