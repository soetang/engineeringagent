"""System clock adapter."""

from __future__ import annotations

import time


class SystemClock:
    """Read wall-clock time from the local system."""

    def now_epoch_seconds(self) -> float:
        """Return the current UTC epoch timestamp in seconds."""
        return time.time()
