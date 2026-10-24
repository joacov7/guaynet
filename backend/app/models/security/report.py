import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, UniqueConstraint
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


class SecurityWeeklyReport(Base):
    """
    Weekly status report sent to the client via Telegram.
    Covers one ISO week (Mon–Sun). Idempotent: one record per subscription per week.
    """
    __tablename__ = "sec_weekly_reports"
    __table_args__ = (
        UniqueConstraint("subscription_id", "week_label", name="uq_sec_weekly_report"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id"), index=True
    )
    # ISO week label, e.g. "2026-W43"
    week_label: Mapped[str] = mapped_column(String(10), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Activity counters for the week
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    armed_count: Mapped[int] = mapped_column(Integer, default=0)
    disarmed_count: Mapped[int] = mapped_column(Integer, default=0)
    alert_count: Mapped[int] = mapped_column(Integer, default=0)
    test_count: Mapped[int] = mapped_column(Integer, default=0)
    battery_warning_count: Mapped[int] = mapped_column(Integer, default=0)

    # JSON list of {zone_number, description} for battery_low events not yet restored
    battery_warnings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    power_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    # JSON list of {occurred_at: ISO str, duration_minutes: int|null, restored: bool}
    power_failures: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
