"""
BEAT Central Monitoring Adapter — Abstract Interface
====================================================

This module defines the contract that any BEAT integration must fulfil.
The real adapter (beat_real.py) will be implemented once official API
documentation is available from the BEAT provider.

Until then, beat_mock.py implements this interface with realistic
simulated data, enabling full development and testing of all
security features without a live BEAT connection.

Rules enforced here:
- No endpoint URLs, API keys or provider-specific formats.
- No assumptions about webhook availability.
- No assumptions about arming/disarming command support.
- All methods that contact BEAT are synchronous (run via asyncio.to_thread).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class BeatEventType(str, Enum):
    armed = "armed"
    disarmed = "disarmed"
    intrusion = "intrusion"
    battery_low = "battery_low"
    battery_restored = "battery_restored"
    power_failure = "power_failure"
    power_restored = "power_restored"
    communication_lost = "communication_lost"
    communication_restored = "communication_restored"
    tamper = "tamper"
    tamper_restored = "tamper_restored"
    zone_open = "zone_open"
    zone_restore = "zone_restore"
    test = "test"
    panic = "panic"
    duress = "duress"
    other = "other"


@dataclass
class BeatEvent:
    account_id: str
    event_type: BeatEventType
    occurred_at: datetime
    zone: Optional[int] = None
    partition: Optional[int] = None
    user_code: Optional[str] = None
    description: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass
class BeatAccountStatus:
    account_id: str

    # None means "the adapter couldn't determine this" — not the same as False.
    armed: Optional[bool] = None
    last_event_at: Optional[datetime] = None
    signal_ok: Optional[bool] = None
    battery_ok: Optional[bool] = None
    power_ok: Optional[bool] = None

    # False when the adapter failed to contact BEAT for this account.
    available: bool = True
    error_message: Optional[str] = None

    # Whether this status came from the mock adapter.
    is_simulated: bool = False


class BeatAdapter(ABC):
    """
    Abstract base for all BEAT integrations.

    Implementations must be thread-safe (called via asyncio.to_thread).
    Methods must not raise on connection failure — return appropriate
    status objects with available=False instead.
    """

    @abstractmethod
    def get_account_status(self, account_id: str) -> BeatAccountStatus:
        """
        Return the current status of a monitored account.
        Must never raise. On failure, return BeatAccountStatus with available=False.
        """
        ...

    @abstractmethod
    def get_recent_events(self, account_id: str, limit: int = 50) -> List[BeatEvent]:
        """
        Return recent events for an account, newest first.
        Must never raise. On failure, return an empty list.
        """
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Verify that the adapter can reach the BEAT service.
        Returns True on success. Must never raise.
        """
        ...

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Human-readable name of this adapter (e.g. 'mock', 'beat_v1')."""
        ...
