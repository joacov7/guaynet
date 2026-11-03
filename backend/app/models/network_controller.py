import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NetworkControllerType(str, enum.Enum):
    unifi_network = "unifi_network"


class NetworkControllerStatus(str, enum.Enum):
    unknown = "unknown"
    online = "online"
    offline = "offline"
    error = "error"


class NetworkController(Base, TimestampMixin):
    """Controller endpoint and encrypted credentials; never store device credentials here."""

    __tablename__ = "network_controllers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    controller_type: Mapped[NetworkControllerType] = mapped_column(
        SAEnum(NetworkControllerType), nullable=False,
        default=NetworkControllerType.unifi_network,
    )
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    site_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    credentials_encrypted: Mapped[Optional[str]] = mapped_column(String(1200), nullable=True)
    verify_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    status: Mapped[NetworkControllerStatus] = mapped_column(
        SAEnum(NetworkControllerStatus), nullable=False,
        default=NetworkControllerStatus.unknown,
    )
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
