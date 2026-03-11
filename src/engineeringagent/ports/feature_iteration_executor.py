"""Feature-iteration execution port used by the application layer."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class FeatureIterationExecutionRequest(BaseModel):
    """Stable request envelope for one feature-iteration execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_path: Path
    run_all: bool = False
    attempt: int
    feedback: str | None
    verbose_output: bool


class FeatureIterationExecutionResult(BaseModel):
    """Stable execution result returned by feature-iteration adapters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: bool
    result: str
    failed_gate: str | None
    next_action: str
    feedback: str | None
    log_path: str | None
    verification_status: str = "not_run"
    verification_failed_command: str | None = None
    reviewer_status: str = "not_run"
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None


class FeatureIterationExecutor(Protocol):
    """Execute one feature iteration without exposing runtime module details."""

    def run(
        self,
        request: FeatureIterationExecutionRequest,
    ) -> FeatureIterationExecutionResult:
        """Execute one normalized feature-iteration request."""
        raise NotImplementedError
