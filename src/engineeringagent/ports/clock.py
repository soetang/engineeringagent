"""Clock port used by orchestration code that records timing metadata."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Provide wall-clock time without binding application code to `time`."""

    def now_epoch_seconds(self) -> float:
        """Return the current UTC epoch timestamp in seconds."""
        raise NotImplementedError
