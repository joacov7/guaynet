"""
BEAT Mock Adapter
=================

Implements BeatAdapter with deterministic simulated data.
Used in development and testing until the real BEAT API is available.

Behaviour:
- get_account_status: returns a predictable status based on account_id.
- get_recent_events: returns a realistic event history seeded from account_id.
- All returned statuses have is_simulated=True so the UI can warn accordingly.
- Never raises exceptions.

NOT suitable for production. Replaced by beat_real.py once the BEAT
provider delivers their official API documentation.
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import List

from app.services.security.beat_adapter import (
    BeatAdapter,
    BeatAccountStatus,
    BeatEvent,
    BeatEventType,
)


def _seed_from(account_id: str) -> int:
    return int(hashlib.md5(account_id.encode()).hexdigest(), 16) % (2 ** 31)


class BeatMockAdapter(BeatAdapter):

    @property
    def adapter_name(self) -> str:
        return "mock"

    def test_connection(self) -> bool:
        return True

    def get_account_status(self, account_id: str) -> BeatAccountStatus:
        rng = random.Random(_seed_from(account_id))
        now = datetime.now(timezone.utc)

        armed = rng.choice([True, False, False])  # usually disarmed
        signal_ok = rng.random() > 0.05           # 95% signal OK
        battery_ok = rng.random() > 0.10          # 90% battery OK
        power_ok = rng.random() > 0.03            # 97% power OK

        last_event_minutes_ago = rng.randint(5, 1440)
        last_event_at = now - timedelta(minutes=last_event_minutes_ago)

        return BeatAccountStatus(
            account_id=account_id,
            armed=armed,
            last_event_at=last_event_at,
            signal_ok=signal_ok,
            battery_ok=battery_ok,
            power_ok=power_ok,
            available=True,
            is_simulated=True,
        )

    def get_recent_events(self, account_id: str, limit: int = 50) -> List[BeatEvent]:
        rng = random.Random(_seed_from(account_id))
        # Anchor to the hour so repeated polls return the same events (and the
        # same idempotency keys) instead of "new" ones every time.
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        event_pool = [
            (BeatEventType.armed,                "Sistema armado"),
            (BeatEventType.disarmed,             "Sistema desarmado"),
            (BeatEventType.disarmed,             "Sistema desarmado"),
            (BeatEventType.disarmed,             "Sistema desarmado"),
            (BeatEventType.zone_open,            "Zona abierta"),
            (BeatEventType.zone_restore,         "Zona restaurada"),
            (BeatEventType.test,                 "Prueba de comunicación"),
            (BeatEventType.power_failure,        "Falla de energía"),
            (BeatEventType.power_restored,       "Energía restaurada"),
            (BeatEventType.battery_low,          "Batería baja"),
            (BeatEventType.communication_lost,   "Pérdida de comunicación"),
            (BeatEventType.communication_restored, "Comunicación restaurada"),
        ]

        events: List[BeatEvent] = []
        offset_minutes = 0
        for _ in range(min(limit, 30)):
            offset_minutes += rng.randint(15, 360)
            etype, edesc = rng.choice(event_pool)
            zone = rng.randint(1, 8) if etype in (
                BeatEventType.zone_open, BeatEventType.zone_restore, BeatEventType.intrusion
            ) else None
            user_code = str(rng.randint(1, 4)) if etype in (
                BeatEventType.armed, BeatEventType.disarmed
            ) else None

            events.append(BeatEvent(
                account_id=account_id,
                event_type=etype,
                occurred_at=now - timedelta(minutes=offset_minutes),
                zone=zone,
                partition=1,
                user_code=user_code,
                description=edesc,
                raw={"simulated": True},
            ))

        return events
