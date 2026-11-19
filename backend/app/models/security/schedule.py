from datetime import date, time
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, SmallInteger, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SecuritySchedule(Base, TimestampMixin):
    """
    Expected opening hours for one weekday (commercial properties).
    Times are Argentina local time. A weekday without a row is a closed day.
    """
    __tablename__ = "sec_schedules"
    __table_args__ = (
        UniqueConstraint("subscription_id", "weekday", name="uq_sec_schedule_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0 = Monday … 6 = Sunday
    open_time: Mapped[time] = mapped_column(Time)
    close_time: Mapped[time] = mapped_column(Time)
    tolerance_minutes: Mapped[int] = mapped_column(Integer, default=15)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Local date of the last "no abrió a horario" notice, so it is sent once per day
    not_opened_notified_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
