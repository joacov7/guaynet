import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client


class DeviceStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    unknown = "unknown"


class UbiquitiDeviceType(str, enum.Enum):
    airmax_ap = "airmax_ap"
    airmax_station = "airmax_station"
    unifi_ap = "unifi_ap"
    unifi_switch = "unifi_switch"
    unifi_gateway = "unifi_gateway"


class MikrotikRouter(Base, TimestampMixin):
    __tablename__ = "mikrotik_routers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=8728)
    username: Mapped[str] = mapped_column(String(100))
    # Stored encrypted via Fernet
    password_encrypted: Mapped[str] = mapped_column(String(600))
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[DeviceStatus] = mapped_column(SAEnum(DeviceStatus), default=DeviceStatus.unknown)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    clients: Mapped[List["Client"]] = relationship(back_populates="router")
    ubiquiti_devices: Mapped[List["UbiquitiDevice"]] = relationship(back_populates="mikrotik_router")


class UbiquitiDevice(Base, TimestampMixin):
    __tablename__ = "ubiquiti_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    host: Mapped[str] = mapped_column(String(255))
    device_type: Mapped[UbiquitiDeviceType] = mapped_column(SAEnum(UbiquitiDeviceType))
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    password_encrypted: Mapped[Optional[str]] = mapped_column(String(600), nullable=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    mikrotik_router_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("mikrotik_routers.id", ondelete="SET NULL"), nullable=True
    )
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[DeviceStatus] = mapped_column(SAEnum(DeviceStatus), default=DeviceStatus.unknown)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cached live fields — updated on test/sync
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    firmware_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ssid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    frequency_mhz: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    channel_width_mhz: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    signal_dbm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ccq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    mikrotik_router: Mapped[Optional["MikrotikRouter"]] = relationship(
        back_populates="ubiquiti_devices", foreign_keys=[mikrotik_router_id]
    )
    clients: Mapped[List["Client"]] = relationship(back_populates="ubiquiti_device")
