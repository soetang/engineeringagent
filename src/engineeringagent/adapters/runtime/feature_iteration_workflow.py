"""Runtime adapter for the application-owned feature-iteration workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from engineeringagent.application.feature_iteration_runtime import (
    FeatureIterationInputs,
    FeatureIterationRequest,
    FeatureIterationResult,
    IterationOutcome,
    IterationPipelineDependencies,
    IterationReport,
    run_feature_iteration_pipeline,
)
from engineeringagent.domain.specification import feature_completion_commit_subject
from engineeringagent.ports import (
    Clock,
    CommitRequest,
    VersionControlGateway,
)


class RuntimeFeatureIterationDependencies(BaseModel):
    """Adapter-owned runtime seams for feature-iteration execution."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    clock: Clock
    evaluate_initial_feature_load: Callable[[Path], Any]
    describe_action: Callable[..., str]
    ready_for_active_iteration: Callable[[str, dict[str, object] | None], bool]
    touch_active_feature_for_iteration: Callable[[dict[str, object], Path], None]
    run_implement_step: Callable[..., Any]
    refresh_feature_after_implement: Callable[[Path, Path], Any]
    should_archive_selected_feature: Callable[[str, dict[str, object] | None], bool]
    archive_completed_feature: Callable[
        [Path, Path], tuple[bool, Path | None, str | None]
    ]
    collect_changed_paths: Callable[[Path], Any]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]
    run_gate_phase: Callable[..., Any]
    build_gate_phase_dependencies: Callable[..., Any]
    run_verification_phase: Callable[..., Any]
    run_reviewer_phase: Callable[..., Any]
    build_reviewer_phase_dependencies: Callable[..., Any]
    run_completion_commit_phase: Callable[..., Any]
    build_completion_phase_dependencies: Callable[..., Any]


def _commit_feature_completion(
    version_control_gateway: VersionControlGateway,
    *,
    project_root: Path,
    feature: dict[str, object],
) -> tuple[bool, str | None, str]:
    """Create the accepted iteration commit for a completed feature."""
    message = feature_completion_commit_subject(feature)
    commit_result = version_control_gateway.commit(
        CommitRequest(
            workspace_path=project_root,
            message=message,
            stage_all=True,
            allow_empty=False,
        )
    )
    output = commit_result.stdout + commit_result.stderr
    if commit_result.commit_created:
        return (True, None, output)
    return (False, commit_result.failure_stage, output)


def build_iteration_pipeline_dependencies(
    runtime_dependencies: RuntimeFeatureIterationDependencies,
    version_control_gateway: VersionControlGateway,
) -> IterationPipelineDependencies:
    """Build the feature-iteration pipeline dependency bundle from runtime seams."""
    return IterationPipelineDependencies(
        clock=runtime_dependencies.clock,
        evaluate_initial_feature_load=runtime_dependencies.evaluate_initial_feature_load,
        describe_action=runtime_dependencies.describe_action,
        ready_for_active_iteration=runtime_dependencies.ready_for_active_iteration,
        touch_active_feature_for_iteration=(
            runtime_dependencies.touch_active_feature_for_iteration
        ),
        run_implement_step=runtime_dependencies.run_implement_step,
        refresh_feature_after_implement=(
            runtime_dependencies.refresh_feature_after_implement
        ),
        should_archive_selected_feature=(
            runtime_dependencies.should_archive_selected_feature
        ),
        archive_completed_feature=runtime_dependencies.archive_completed_feature,
        run_gate_phase=runtime_dependencies.run_gate_phase,
        gate_phase_dependencies=runtime_dependencies.build_gate_phase_dependencies(
            restore_archived_feature=runtime_dependencies.restore_archived_feature,
            collect_changed_paths=runtime_dependencies.collect_changed_paths,
        ),
        run_verification_phase=runtime_dependencies.run_verification_phase,
        run_reviewer_phase=runtime_dependencies.run_reviewer_phase,
        reviewer_phase_dependencies=(
            runtime_dependencies.build_reviewer_phase_dependencies(
                collect_changed_paths=runtime_dependencies.collect_changed_paths,
                restore_archived_feature=runtime_dependencies.restore_archived_feature,
            )
        ),
        run_completion_commit_phase=runtime_dependencies.run_completion_commit_phase,
        completion_phase_dependencies=(
            runtime_dependencies.build_completion_phase_dependencies(
                commit_feature_completion=lambda project_root, feature: (
                    _commit_feature_completion(
                        version_control_gateway,
                        project_root=project_root,
                        feature=feature,
                    )
                ),
                restore_archived_feature=runtime_dependencies.restore_archived_feature,
            )
        ),
    )


class RuntimeFeatureIterationWorkflow:
    """Execute feature iterations through the runtime pipeline adapter."""

    def __init__(
        self,
        *,
        version_control_gateway: VersionControlGateway,
        iteration_report_publisher: Callable[[IterationReport], IterationOutcome],
        runtime_dependencies: RuntimeFeatureIterationDependencies,
    ) -> None:
        self._version_control_gateway = version_control_gateway
        self._iteration_report_publisher = iteration_report_publisher
        self._runtime_dependencies = runtime_dependencies

    def run(self, request: FeatureIterationRequest) -> FeatureIterationResult:
        """Execute one feature iteration request and publish its report."""
        report = run_feature_iteration_pipeline(
            FeatureIterationInputs(
                project_root=request.project_root,
                feature_path=request.feature_path,
                run_all=request.run_all,
                attempt=request.attempt,
                feedback=request.feedback,
                verbose_output=request.verbose_output,
            ),
            build_iteration_pipeline_dependencies(
                self._runtime_dependencies,
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
