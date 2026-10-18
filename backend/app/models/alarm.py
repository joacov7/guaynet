import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.router import MikrotikRouter


class AlarmType(str, enum.Enum):
    router_offline = "router_offline"
    cpu_high = "cpu_high"
    wan_down = "wan_down"


class AlarmStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"


class Alarm(Base, TimestampMixin):
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(ForeignKey("mikrotik_routers.id"), index=True)
    type: Mapped[AlarmType] = mapped_column(SAEnum(AlarmType), index=True)
    status: Mapped[AlarmStatus] = mapped_column(SAEnum(AlarmStatus), default=AlarmStatus.active, index=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    router: Mapped["MikrotikRouter"] = relationship("MikrotikRouter", lazy="select")
