from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AutomationLog(Base, TimestampMixin):
    __tablename__ = "automation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20))  # success | error | skipped
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected: Mapped[int] = mapped_column(Integer, default=0)
