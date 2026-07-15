"""High-resolution timing utilities."""

from __future__ import annotations

import time
from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return the current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def monotonic_ns() -> int:
    """Return a monotonic clock value in nanoseconds for duration measurement."""
    return time.monotonic_ns()


def duration_ms(start_ns: int, end_ns: int | None = None) -> float:
    """Calculate duration in milliseconds from nanosecond monotonic timestamps.

    Args:
        start_ns: Start time from monotonic_ns().
        end_ns: End time from monotonic_ns(). If None, uses current time.

    Returns:
        Duration in milliseconds with microsecond precision.
    """
    if end_ns is None:
        end_ns = monotonic_ns()
    return (end_ns - start_ns) / 1_000_000


def timestamp_iso(dt: datetime | None = None) -> str:
    """Convert datetime to ISO 8601 string. Defaults to now_utc()."""
    if dt is None:
        dt = now_utc()
    return dt.isoformat()
