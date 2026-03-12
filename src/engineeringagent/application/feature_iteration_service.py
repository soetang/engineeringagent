"""Application service for feature-iteration execution requests."""

from __future__ import annotations

from engineeringagent.application.feature_iteration_runtime import (
    FeatureIterationRequest,
    FeatureIterationResult,
)
from engineeringagent.ports import (
    FeatureIterationExecutionRequest,
    FeatureIterationExecutor,
)


class FeatureIterationService:
    """Own feature-iteration sequencing behind a stable application contract."""

    def __init__(
        self,
        *,
        executor: FeatureIterationExecutor,
    ) -> None:
        self._executor = executor

    def run(self, request: FeatureIterationRequest) -> FeatureIterationResult:
        """Execute one feature iteration through the runtime pipeline."""
        outcome = self._executor.run(
            FeatureIterationExecutionRequest(
                project_root=request.project_root,
                feature_path=request.feature_path,
                run_all=request.run_all,
                attempt=request.attempt,
                feedback=request.feedback,
                verbose_output=request.verbose_output,
            )
        )
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
