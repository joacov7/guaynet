import enum
from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice
    from app.models.plan import Plan
    from app.models.router import MikrotikRouter, UbiquitiDevice


class ClientStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    cancelled = "cancelled"


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    dni: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    cuit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ip_address: Mapped[str] = mapped_column(String(45), unique=True, index=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    router_id: Mapped[int] = mapped_column(ForeignKey("mikrotik_routers.id"))
    ubiquiti_device_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ubiquiti_devices.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[ClientStatus] = mapped_column(SAEnum(ClientStatus), default=ClientStatus.active)
    service_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    billing_day: Mapped[int] = mapped_column(Integer, default=1)

    plan: Mapped["Plan"] = relationship(back_populates="clients")
    router: Mapped["MikrotikRouter"] = relationship(back_populates="clients")
    ubiquiti_device: Mapped[Optional["UbiquitiDevice"]] = relationship(back_populates="clients")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="client")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def mikrotik_queue_name(self) -> str:
        return f"gw-{self.id}"

    @property
    def mikrotik_target(self) -> str:
        return f"{self.ip_address}/32"
