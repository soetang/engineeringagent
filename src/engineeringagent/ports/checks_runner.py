"""Checks execution port used by the application layer."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from engineeringagent.checks import ChecksRunResult, HarnessCheckPhase


class ChecksRunRequest(BaseModel):
    """Stable request envelope for deterministic checks execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    selected_checks: list[str] | None
    check_id: str | None
    feature_path: str | None
    phase: HarnessCheckPhase
    base: str | None
    head: str | None
    verbose_output: bool
    dry_run: bool


class ChecksRunner(Protocol):
    """Run deterministic checks without exposing adapter details."""

    def run(self, request: ChecksRunRequest) -> ChecksRunResult:
        """Execute one checks request."""
        raise NotImplementedError

    def reviewers_group_selected(self, selected_checks: list[str] | None) -> bool:
        """Return whether the selected groups require a feature path."""
        raise NotImplementedError
