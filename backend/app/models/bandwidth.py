from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BandwidthSample(Base):
    __tablename__ = "bandwidth_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(Integer, ForeignKey("mikrotik_routers.id"), nullable=False)
    client_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("clients.id"), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(200), nullable=False)
    upload_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    download_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
