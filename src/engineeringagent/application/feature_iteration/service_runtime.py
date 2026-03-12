"""Internal feature-iteration service wiring helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.domain.specification import feature_completion_commit_subject
from engineeringagent.ports import CommitRequest, ProgressJournal, VersionControlGateway

from .contracts import IterationReport
from .pipeline import IterationPipelineDependencies
from .runtime_dependencies import FeatureIterationRuntimeDependencies


def commit_feature_completion(
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


def persist_iteration_report(
    progress_journal: ProgressJournal,
    report: IterationReport,
) -> None:
    """Persist the structured iteration report through the journal port."""
    progress_journal.write_iteration_report(
        project_root=report.telemetry_inputs.iteration_inputs.project_root,
        feature_id=report.feature_id,
        payload=report.model_dump(mode="json"),
    )


def build_iteration_pipeline_dependencies(
    runtime_dependencies: FeatureIterationRuntimeDependencies,
    *,
    version_control_gateway: VersionControlGateway,
) -> IterationPipelineDependencies:
    """Build the pipeline dependency bundle from runtime seams."""
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
                    commit_feature_completion(
                        version_control_gateway,
                        project_root=project_root,
                        feature=feature,
                    )
                ),
                restore_archived_feature=runtime_dependencies.restore_archived_feature,
            )
        ),
    )


def build_iteration_report_observers(
    runtime_dependencies: FeatureIterationRuntimeDependencies,
    *,
    progress_journal: ProgressJournal,
) -> Any:
    """Build the default report observers from runtime seams."""
    observer_dependencies = runtime_dependencies.observer_dependencies_type(
        write_iteration_telemetry=(
            lambda telemetry_inputs: runtime_dependencies.write_iteration_telemetry(
                telemetry_inputs,
                git_head_resolver=runtime_dependencies.git_head_short,
            )
        ),
        persist_iteration_report=(
            lambda report: persist_iteration_report(progress_journal, report)
        ),
        git_head_resolver=runtime_dependencies.git_head_short,
        print_summary=runtime_dependencies.print_summary,
    )
    return runtime_dependencies.build_iteration_report_observers(observer_dependencies)
