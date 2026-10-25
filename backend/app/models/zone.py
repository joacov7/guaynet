from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.router import MikrotikRouter


class Zone(Base, TimestampMixin):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="#1677ff")
    router_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mikrotik_routers.id"), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    router: Mapped[Optional["MikrotikRouter"]] = relationship("MikrotikRouter", lazy="select")
    clients: Mapped[List["Client"]] = relationship("Client", back_populates="zone", lazy="select")
