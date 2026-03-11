from __future__ import annotations

from datetime import datetime, timezone


def utc_iso_from_epoch_sec(epoch_sec: int) -> str:
    """Return an RFC3339 UTC timestamp with second precision."""
    return (
        datetime.fromtimestamp(epoch_sec, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

