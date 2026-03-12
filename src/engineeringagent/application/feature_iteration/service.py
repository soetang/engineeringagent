"""Application service for feature-iteration execution requests."""

from __future__ import annotations

from engineeringagent.ports import VersionControlGateway

from .contracts import FeatureIterationInputs, FeatureIterationRequest, FeatureIterationResult
from .report_publisher import IterationReportPublisher
from .runtime_dependencies import FeatureIterationRuntimeDependencies


class FeatureIterationService:
    """Own feature-iteration sequencing behind a stable application contract."""

    def __init__(
        self,
        *,
        version_control_gateway: VersionControlGateway,
        iteration_report_publisher: IterationReportPublisher,
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
