"""Application service for feature-iteration execution requests."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.ports import (
    FeatureIterationExecutionRequest,
    FeatureIterationExecutor,
)


class FeatureIterationRequest(BaseModel):
    """Typed input for one feature-iteration execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_path: Path
    run_all: bool = False
    attempt: int
    feedback: str | None
    verbose_output: bool


class FeatureIterationResult(BaseModel):
    """Stable application result for one feature-iteration execution."""

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


class FeatureIterationService:
    """Own feature-iteration requests behind a stable application contract."""

    def __init__(self, feature_iteration_executor: FeatureIterationExecutor) -> None:
        self._feature_iteration_executor = feature_iteration_executor

    def run(self, request: FeatureIterationRequest) -> FeatureIterationResult:
        """Execute one feature iteration through the injected runtime boundary."""
        result = self._feature_iteration_executor.run(
            FeatureIterationExecutionRequest(
                project_root=request.project_root,
                feature_path=request.feature_path,
                run_all=request.run_all,
                attempt=request.attempt,
                feedback=request.feedback,
                verbose_output=request.verbose_output,
            )
        )
        return FeatureIterationResult.model_validate(result.model_dump())
