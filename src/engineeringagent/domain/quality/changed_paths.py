"""Quality-domain models for deterministic changed-path discovery."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


FALLBACK_CHANGE_DISCOVERY_REASON = "fallback_run_all_change_discovery_failed"


class ChangedPathsResult(BaseModel):
    """Deterministic changed-path discovery result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: tuple[str, ...]
    run_all: bool
    reason: str | None
