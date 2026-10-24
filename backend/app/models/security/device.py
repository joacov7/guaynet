import enum
from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.security.subscription import SecuritySubscription


class SecurityDeviceType(str, enum.Enum):
    panel = "panel"             # Alarm control panel
    sensor_motion = "sensor_motion"
    sensor_magnetic = "sensor_magnetic"
    sensor_smoke = "sensor_smoke"
    sensor_glass = "sensor_glass"
    siren = "siren"
    keypad = "keypad"
    camera = "camera"
    communicator = "communicator"  # GSM/IP communicator module
    other = "other"


class SecurityDevice(Base, TimestampMixin):
    """
    Physical device installed at a property.
    The installation record (ficha técnica) lives here.
    """
    __tablename__ = "sec_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), index=True
    )
    device_type: Mapped[SecurityDeviceType] = mapped_column(
        SAEnum(SecurityDeviceType, native_enum=False), index=True
    )
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    firmware_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    install_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    warranty_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    location_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    subscription: Mapped["SecuritySubscription"] = relationship(
        "SecuritySubscription", back_populates="devices"
    )
    zones: Mapped[List["DeviceZone"]] = relationship(
        "DeviceZone", back_populates="device", cascade="all, delete-orphan"
    )


class DeviceZone(Base):
    """
    Zone configured on an alarm panel.
    Zone names and types are set here for display purposes.
    """
    __tablename__ = "sec_device_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("sec_devices.id", ondelete="CASCADE"), index=True
    )
    zone_number: Mapped[int] = mapped_column(Integer)
    zone_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zone_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    device: Mapped["SecurityDevice"] = relationship("SecurityDevice", back_populates="zones")
