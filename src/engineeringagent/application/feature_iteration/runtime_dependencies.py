"""Application-owned wiring helpers for feature-iteration runtime orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.specification import feature_completion_commit_subject
from engineeringagent.ports import Clock, CommitRequest, VersionControlGateway

from engineeringagent.domain.audit.iteration_records import (
    IterationOutcome,
    IterationReport,
)
from .pipeline import IterationPipelineDependencies


class FeatureIterationDependencies(BaseModel):
    """Application-owned seams for feature-iteration orchestration."""

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


IterationReportPublisher = Callable[[IterationReport], IterationOutcome]


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


def build_feature_iteration_pipeline_dependencies(
    dependencies: FeatureIterationDependencies,
    version_control_gateway: VersionControlGateway,
) -> IterationPipelineDependencies:
    """Build the pipeline dependency bundle used by the application service."""
    return IterationPipelineDependencies(
        clock=dependencies.clock,
        evaluate_initial_feature_load=dependencies.evaluate_initial_feature_load,
        describe_action=dependencies.describe_action,
        ready_for_active_iteration=dependencies.ready_for_active_iteration,
        touch_active_feature_for_iteration=(
            dependencies.touch_active_feature_for_iteration
        ),
        run_implement_step=dependencies.run_implement_step,
        refresh_feature_after_implement=dependencies.refresh_feature_after_implement,
        should_archive_selected_feature=dependencies.should_archive_selected_feature,
        archive_completed_feature=dependencies.archive_completed_feature,
        run_gate_phase=dependencies.run_gate_phase,
        gate_phase_dependencies=dependencies.build_gate_phase_dependencies(
            restore_archived_feature=dependencies.restore_archived_feature,
            collect_changed_paths=dependencies.collect_changed_paths,
        ),
        run_verification_phase=dependencies.run_verification_phase,
        run_reviewer_phase=dependencies.run_reviewer_phase,
        reviewer_phase_dependencies=dependencies.build_reviewer_phase_dependencies(
            collect_changed_paths=dependencies.collect_changed_paths,
            restore_archived_feature=dependencies.restore_archived_feature,
        ),
        run_completion_commit_phase=dependencies.run_completion_commit_phase,
        completion_phase_dependencies=dependencies.build_completion_phase_dependencies(
            commit_feature_completion=lambda project_root, feature: (
                _commit_feature_completion(
                    version_control_gateway,
                    project_root=project_root,
                    feature=feature,
                )
            ),
            restore_archived_feature=dependencies.restore_archived_feature,
        ),
    )
