import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityMonthlyReportStatus(str, enum.Enum):
    generating = "generating"
    ready = "ready"
    failed = "failed"


class SecurityMonthlyReport(Base):
    """
    Generated monthly report for a security subscription.
    Created by the Celery beat task at month end.
    PDF stored at file_path (relative to uploads dir).
    """
    __tablename__ = "sec_monthly_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id"), index=True
    )
    period: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[SecurityMonthlyReportStatus] = mapped_column(
        SAEnum(SecurityMonthlyReportStatus, native_enum=False),
        default=SecurityMonthlyReportStatus.generating,
    )
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    alert_count: Mapped[int] = mapped_column(Integer, default=0)
    test_count: Mapped[int] = mapped_column(Integer, default=0)
    visit_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
