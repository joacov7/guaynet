import enum
from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EquipmentCondition(str, enum.Enum):
    new = "new"
    good = "good"
    damaged = "damaged"
    scrapped = "scrapped"


class EquipmentStatus(str, enum.Enum):
    in_stock = "in_stock"
    assigned = "assigned"
    returned = "returned"
    lost = "lost"


class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_cost: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    condition: Mapped[EquipmentCondition] = mapped_column(SAEnum(EquipmentCondition), default=EquipmentCondition.new)
    status: Mapped[EquipmentStatus] = mapped_column(SAEnum(EquipmentStatus), default=EquipmentStatus.in_stock, index=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
