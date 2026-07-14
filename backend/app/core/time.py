"""Time helpers for consistent UTC timestamps."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """Return a naive UTC datetime for legacy DateTime columns."""
    return utc_now().replace(tzinfo=None)
