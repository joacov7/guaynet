"""Utilities for stable DHCP/CPE identity handling."""
import re
from typing import Optional


def normalize_mac(value: Optional[str]) -> str:
    """Return canonical AA:BB:CC:DD:EE:FF form; empty string for invalid input."""
    raw = (value or "").strip()
    if not raw or not re.fullmatch(r"[0-9a-fA-F:.-]+", raw):
        return ""
    compact = re.sub(r"[:.-]", "", raw)
    if len(compact) != 12 or not re.fullmatch(r"[0-9a-fA-F]{12}", compact):
        return ""
    compact = compact.lower()
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))
