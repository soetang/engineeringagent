"""Specification-domain outcomes for feature document state transitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class InitialFeatureLoadOutcome(BaseModel):
    """Outcome of loading the selected feature document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: dict[str, Any] | None
    result: str
    failed_gate: str | None
    feedback: str | None


class PostImplementFeatureOutcome(BaseModel):
    """Outcome from refreshing feature state after implementation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: dict[str, Any] | None
    archived_in_iteration: bool
    archived_path: Path | None
    result: str
    failed_gate: str | None
    feedback: str | None
