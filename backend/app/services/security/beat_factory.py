"""
BEAT Adapter Factory
====================

Returns the appropriate adapter based on configuration.
Set BEAT_ADAPTER=real in .env to use the real adapter (not yet implemented).
Default is "mock" for safe development.
"""

import os

from app.services.security.beat_adapter import BeatAdapter


def get_beat_adapter() -> BeatAdapter:
    """
    Returns the configured BEAT adapter instance.

    BEAT_ADAPTER environment variable controls which adapter is used:
    - "mock" (default): BeatMockAdapter — simulated data, safe for development.
    - "real": BeatRealAdapter — requires real BEAT API credentials (not yet implemented).
    """
    adapter_name = os.getenv("BEAT_ADAPTER", "mock").lower()

    if adapter_name == "mock":
        from app.services.security.beat_mock import BeatMockAdapter
        return BeatMockAdapter()

    if adapter_name == "real":
        # beat_real.py will be implemented once BEAT API documentation is available.
        # Until then, importing it raises ImportError intentionally.
        try:
            from app.services.security.beat_real import BeatRealAdapter  # type: ignore
            return BeatRealAdapter()
        except ImportError:
            raise RuntimeError(
                "BEAT_ADAPTER=real was set but beat_real.py is not yet implemented. "
                "Set BEAT_ADAPTER=mock for development."
            )

    raise ValueError(f"Unknown BEAT_ADAPTER value: {adapter_name!r}. Use 'mock' or 'real'.")
