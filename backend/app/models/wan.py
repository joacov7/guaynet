from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, BigInteger
from sqlalchemy.orm import relationship
from app.models.base import Base


class WanInterface(Base):
    __tablename__ = "wan_interfaces"

    id = Column(Integer, primary_key=True, index=True)
    router_id = Column(Integer, ForeignKey("mikrotik_routers.id", ondelete="CASCADE"), nullable=False)
    interface_name = Column(String(64), nullable=False)
    display_name = Column(String(64), nullable=True)
    weight = Column(Integer, default=1)
    cap_gb = Column(Integer, nullable=True)
    manual_override = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    # Accumulated bytes this billing cycle (reset on 1st of month)
    accumulated_rx_bytes = Column(BigInteger, default=0)
    accumulated_tx_bytes = Column(BigInteger, default=0)
    # Last known raw counter from router (for delta calculation)
    last_rx_bytes = Column(BigInteger, nullable=True)
    last_tx_bytes = Column(BigInteger, nullable=True)

    router = relationship("MikrotikRouter", back_populates="wan_interfaces")
    schedules = relationship("WanSchedule", back_populates="wan_interface", cascade="all, delete-orphan")


class WanSchedule(Base):
    __tablename__ = "wan_schedules"

    id = Column(Integer, primary_key=True, index=True)
    wan_interface_id = Column(Integer, ForeignKey("wan_interfaces.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(10), nullable=False)  # "enable" | "disable"
    # Days as comma-separated: "mon,tue,wed,thu,fri,sat,sun"
    days = Column(String(64), nullable=False, default="mon,tue,wed,thu,fri,sat,sun")
    time_start = Column(String(8), nullable=False)  # "HH:MM:SS"
    time_end = Column(String(8), nullable=False)

    wan_interface = relationship("WanInterface", back_populates="schedules")
