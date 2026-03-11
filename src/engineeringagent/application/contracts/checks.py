"""Contracts for deterministic checks execution."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.quality import ChecksRunResult, HarnessCheckPhase


class RunChecksRequest(BaseModel):
    """Typed input for one checks execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    selected_checks: list[str] | None
    check_id: str | None
    feature_path: str | None
    phase: HarnessCheckPhase
    all_phases: bool
    base: str | None
    head: str | None
    verbose_output: bool
    dry_run: bool


class RunChecksResult(BaseModel):
    """Stable application result for one checks execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_results: tuple[tuple[HarnessCheckPhase, ChecksRunResult], ...]
    result: ChecksRunResult
    failed_phase: HarnessCheckPhase | None
    failed_runtime_message: str | None
