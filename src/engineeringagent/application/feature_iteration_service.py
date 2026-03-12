"""Application service for feature-iteration execution requests."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict

class FeatureIterationRequest(BaseModel):
    """Typed input for one feature-iteration workflow request."""

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


FeatureIterationWorkflow = Callable[[FeatureIterationRequest], FeatureIterationResult]


class FeatureIterationService:
    """Own feature-iteration sequencing behind a stable application contract."""

    def __init__(
        self,
        *,
        workflow: FeatureIterationWorkflow,
    ) -> None:
        self._workflow = workflow

    def run(self, request: FeatureIterationRequest) -> FeatureIterationResult:
        """Execute one feature iteration through the runtime pipeline."""
        return self._workflow(request)
