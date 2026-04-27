from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Speeds in Mbps
    download_mbps: Mapped[int] = mapped_column(Integer)
    upload_mbps: Mapped[int] = mapped_column(Integer)

    # Burst — optional
    burst_download_mbps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    burst_upload_mbps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Average usage threshold below which burst is allowed
    burst_threshold_mbps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    burst_time_seconds: Mapped[int] = mapped_column(Integer, default=10)

    price: Mapped[float] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    clients: Mapped[List["Client"]] = relationship(back_populates="plan")

    @property
    def mikrotik_max_limit(self) -> str:
        return f"{self.download_mbps}M/{self.upload_mbps}M"

    @property
    def mikrotik_burst_limit(self) -> Optional[str]:
        if self.burst_download_mbps and self.burst_upload_mbps:
            return f"{self.burst_download_mbps}M/{self.burst_upload_mbps}M"
        return None

    @property
    def mikrotik_burst_threshold(self) -> Optional[str]:
        if self.burst_threshold_mbps:
            return f"{self.burst_threshold_mbps}M/{self.burst_threshold_mbps}M"
        return None

    @property
    def mikrotik_burst_time(self) -> str:
        return f"{self.burst_time_seconds}/{self.burst_time_seconds}"
