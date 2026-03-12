"""Bootstrap-owned assembly for explicit feature-iteration dependencies."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.documents import filesystem_feature_state
from engineeringagent.adapters.progress import write_iteration_telemetry
from engineeringagent.application.feature_iteration import (
    FeatureIterationRuntimeDependencies,
    IterationPipelineDependencies,
    IterationReport,
    run_feature_iteration_pipeline,
)
from engineeringagent.bootstrap.iteration_reporting import (
    DefaultObserverDependencies,
    build_default_iteration_report_observers,
    publish_iteration_report,
)
from engineeringagent.checks import collect_changed_paths
from engineeringagent.domain.specification import feature_completion_commit_subject
from engineeringagent.adapters.runtime.iteration_phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    run_completion_commit_phase,
    run_gate_phase,
    run_reviewer_phase,
    run_verification_phase,
)
from engineeringagent.bootstrap import runtime_support
from engineeringagent.ports import (
    Clock,
    CommitRequest,
    ProgressJournal,
    VersionControlGateway,
)


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


def _persist_iteration_report(
    progress_journal: ProgressJournal,
    report: IterationReport,
) -> None:
    """Persist the structured iteration report through the journal port."""
    progress_journal.write_iteration_report(
        project_root=report.telemetry_inputs.iteration_inputs.project_root,
        feature_id=report.feature_id,
        payload=report.model_dump(mode="json"),
    )


def _build_iteration_pipeline_dependencies(
    runtime_dependencies: FeatureIterationRuntimeDependencies,
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


def _build_iteration_report_observers(
    runtime_dependencies: FeatureIterationRuntimeDependencies,
    progress_journal: ProgressJournal,
) -> object:
    """Build the default iteration-report observers from bootstrap seams."""
    observer_dependencies = runtime_dependencies.observer_dependencies_type(
        write_iteration_telemetry=(
            lambda telemetry_inputs: runtime_dependencies.write_iteration_telemetry(
                telemetry_inputs,
                git_head_resolver=runtime_dependencies.git_head_short,
            )
        ),
        persist_iteration_report=(
            lambda report: _persist_iteration_report(progress_journal, report)
        ),
        git_head_resolver=runtime_dependencies.git_head_short,
        print_summary=runtime_dependencies.print_summary,
    )
    return build_default_iteration_report_observers(observer_dependencies)


def build_feature_iteration_dependencies(
    *,
    clock: Clock,
) -> FeatureIterationRuntimeDependencies:
    """Build the default runtime seam bundle for feature iterations."""
    return FeatureIterationRuntimeDependencies(
        clock=clock,
        evaluate_initial_feature_load=filesystem_feature_state.evaluate_initial_feature_load,
        describe_action=runtime_support.describe_action,
        ready_for_active_iteration=filesystem_feature_state.ready_for_active_iteration,
        touch_active_feature_for_iteration=(
            filesystem_feature_state.touch_active_feature_for_iteration
        ),
        run_implement_step=runtime_support.run_implement_step,
        refresh_feature_after_implement=(
            filesystem_feature_state.refresh_feature_after_implement
        ),
        should_archive_selected_feature=(
            filesystem_feature_state.should_archive_selected_feature
        ),
        archive_completed_feature=filesystem_feature_state.archive_completed_feature,
        collect_changed_paths=collect_changed_paths,
        restore_archived_feature=filesystem_feature_state.restore_archived_feature,
        run_feature_iteration_pipeline=run_feature_iteration_pipeline,
        run_gate_phase=run_gate_phase,
        build_gate_phase_dependencies=GatePhaseDependencies,
        run_verification_phase=run_verification_phase,
        run_reviewer_phase=run_reviewer_phase,
        build_reviewer_phase_dependencies=ReviewerPhaseDependencies,
        run_completion_commit_phase=run_completion_commit_phase,
        build_completion_phase_dependencies=CompletionPhaseDependencies,
        git_head_short=runtime_support.git_head_short,
        print_summary=runtime_support.print_summary,
        observer_dependencies_type=DefaultObserverDependencies,
        write_iteration_telemetry=write_iteration_telemetry,
        build_iteration_pipeline_dependencies=_build_iteration_pipeline_dependencies,
        build_iteration_report_observers=_build_iteration_report_observers,
        publish_iteration_report=publish_iteration_report,
    )
