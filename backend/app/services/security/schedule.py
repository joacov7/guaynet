"""
Commercial opening schedule ("alertas de apertura/cierre").

Rules (Argentina local time, UTC-3, no DST):
- A weekday with an enabled row is open between open_time and close_time.
- A weekday without an enabled row is a closed day.
- Disarming outside [open - tolerance, close + tolerance] is a violation.
- Still disarmed after close + tolerance is a violation ("no se cerró").
- Still armed after open + tolerance only notifies the owner ("no abrió"):
  it is a business notice, not an emergency, so it creates no alert.
Schedules only apply when the subscription has at least one row configured.
"""
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.schedule import SecuritySchedule

AR_TZ = timezone(timedelta(hours=-3))

WEEKDAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class ScheduleDay(BaseModel):
    weekday: int = Field(ge=0, le=6)
    open_time: time
    close_time: time
    tolerance_minutes: int = Field(default=15, ge=0, le=180)
    enabled: bool = True

    @model_validator(mode="after")
    def _check_times(self):
        if self.open_time >= self.close_time:
            raise ValueError(
                f"El {WEEKDAY_NAMES[self.weekday]} la apertura debe ser anterior al cierre"
            )
        return self


class ScheduleDayResponse(ScheduleDay):
    pass


# ── Pure rules ────────────────────────────────────────────────────────────────

def _window(day: SecuritySchedule, on: datetime):
    tol = timedelta(minutes=day.tolerance_minutes or 0)
    start = datetime.combine(on.date(), day.open_time, tzinfo=AR_TZ) - tol
    end = datetime.combine(on.date(), day.close_time, tzinfo=AR_TZ) + tol
    return start, end


def disarm_violation(days: Dict[int, SecuritySchedule], when: datetime) -> Optional[str]:
    """Return a human reason if disarming at `when` breaks the schedule, else None."""
    local = when.astimezone(AR_TZ)
    day = days.get(local.weekday())
    hhmm = local.strftime("%H:%M")
    if day is None or not day.enabled:
        return f"Desarmado a las {hhmm} en día cerrado ({WEEKDAY_NAMES[local.weekday()]})"
    start, end = _window(day, local)
    if local < start:
        return f"Desarmado a las {hhmm}, antes de la apertura ({day.open_time.strftime('%H:%M')})"
    if local > end:
        return f"Desarmado a las {hhmm}, después del cierre ({day.close_time.strftime('%H:%M')})"
    return None


def opening_window(days: Dict[int, SecuritySchedule], now: datetime):
    """
    (schedule_row, deadline) if `now` is between open + tolerance and close on an
    open day — i.e. the business should already be open — else None.
    """
    local = now.astimezone(AR_TZ)
    day = days.get(local.weekday())
    if day is None or not day.enabled:
        return None
    tol = timedelta(minutes=day.tolerance_minutes or 0)
    deadline = datetime.combine(local.date(), day.open_time, tzinfo=AR_TZ) + tol
    close = datetime.combine(local.date(), day.close_time, tzinfo=AR_TZ)
    if deadline <= local < close:
        return day, deadline
    return None


def closing_deadline(days: Dict[int, SecuritySchedule], now: datetime) -> Optional[datetime]:
    """Close time + tolerance for today, or None if today is a closed day."""
    local = now.astimezone(AR_TZ)
    day = days.get(local.weekday())
    if day is None or not day.enabled:
        return None
    return _window(day, local)[1]


# ── Persistence ───────────────────────────────────────────────────────────────

async def get_schedule(db: AsyncSession, subscription_id: int) -> List[SecuritySchedule]:
    result = await db.execute(
        select(SecuritySchedule)
        .where(SecuritySchedule.subscription_id == subscription_id)
        .order_by(SecuritySchedule.weekday)
    )
    return result.scalars().all()


async def replace_schedule(
    db: AsyncSession, subscription_id: int, days: List[ScheduleDay]
) -> List[SecuritySchedule]:
    weekdays = [d.weekday for d in days]
    if len(weekdays) != len(set(weekdays)):
        raise HTTPException(status_code=422, detail="Hay días repetidos en el horario")

    await db.execute(
        delete(SecuritySchedule).where(SecuritySchedule.subscription_id == subscription_id)
    )
    for d in days:
        db.add(SecuritySchedule(subscription_id=subscription_id, **d.model_dump()))
    await db.commit()
    return await get_schedule(db, subscription_id)


async def schedules_by_subscription(
    db: AsyncSession, subscription_ids: Iterable[int]
) -> Dict[int, Dict[int, SecuritySchedule]]:
    """{subscription_id: {weekday: row}} for subscriptions with schedule_alerts enabled."""
    from app.models.security.subscription import SecurityFeature, SecurityFeatureName

    ids = set(subscription_ids)
    if not ids:
        return {}
    enabled = await db.execute(
        select(SecurityFeature.subscription_id).where(
            SecurityFeature.subscription_id.in_(ids),
            SecurityFeature.feature_name == SecurityFeatureName.schedule_alerts,
            SecurityFeature.enabled == True,
        )
    )
    enabled_ids = {row[0] for row in enabled.all()}
    if not enabled_ids:
        return {}
    rows = await db.execute(
        select(SecuritySchedule).where(SecuritySchedule.subscription_id.in_(enabled_ids))
    )
    out: Dict[int, Dict[int, SecuritySchedule]] = {}
    for r in rows.scalars().all():
        out.setdefault(r.subscription_id, {})[r.weekday] = r
    return out
