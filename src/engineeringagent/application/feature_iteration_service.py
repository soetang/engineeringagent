"""Application service for feature-iteration execution requests."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict

from engineeringagent.ports import VersionControlGateway

from .feature_iteration import FeatureIterationInputs, IterationOutcome, IterationReport
from .feature_iteration.runtime_dependencies import FeatureIterationRuntimeDependencies


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
    """Own feature-iteration sequencing behind a stable application contract."""

    def __init__(
        self,
        *,
        version_control_gateway: VersionControlGateway,
        iteration_report_publisher: Callable[[IterationReport], IterationOutcome],
        runtime_dependencies: FeatureIterationRuntimeDependencies,
    ) -> None:
        self._version_control_gateway = version_control_gateway
        self._iteration_report_publisher = iteration_report_publisher
        self._runtime_dependencies = runtime_dependencies

    def run(self, request: FeatureIterationRequest) -> FeatureIterationResult:
        """Execute one feature iteration through the runtime pipeline."""
        dependencies = self._runtime_dependencies
        report = dependencies.run_feature_iteration_pipeline(
            FeatureIterationInputs(
                project_root=request.project_root,
                feature_path=request.feature_path,
                run_all=request.run_all,
                attempt=request.attempt,
                feedback=request.feedback,
                verbose_output=request.verbose_output,
            ),
            dependencies.build_iteration_pipeline_dependencies(
                dependencies,
                self._version_control_gateway,
            ),
        )
        outcome = self._iteration_report_publisher(report)
        return FeatureIterationResult(
            completed=outcome.completed,
            result=outcome.result,
            failed_gate=outcome.failed_gate,
            next_action=outcome.next_action,
            feedback=outcome.feedback,
            log_path=outcome.log_path,
            verification_status=outcome.verification_status,
            verification_failed_command=outcome.verification_failed_command,
            reviewer_status=outcome.reviewer_status,
            reviewer_decision=outcome.reviewer_decision,
            failed_reviewer_id=outcome.failed_reviewer_id,
        )
