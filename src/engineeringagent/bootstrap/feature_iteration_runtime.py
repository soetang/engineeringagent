"""Bootstrap-owned assembly for explicit feature-iteration dependencies."""

from __future__ import annotations

from engineeringagent.adapters.documents import filesystem_feature_state
from engineeringagent.adapters.progress import write_iteration_telemetry
from engineeringagent.application import FeatureIterationRuntimeDependencies
from engineeringagent.application.feature_iteration import (
    run_feature_iteration_pipeline,
)
from engineeringagent.bootstrap.iteration_reporting import (
    DefaultObserverDependencies,
    build_default_iteration_report_observers,
    publish_iteration_report,
)
from engineeringagent.checks import collect_changed_paths
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


def build_feature_iteration_runtime_dependencies() -> (
    FeatureIterationRuntimeDependencies
):
    """Build the default runtime seam bundle for feature iterations."""
    return FeatureIterationRuntimeDependencies(
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
        build_iteration_report_observers=build_default_iteration_report_observers,
        publish_iteration_report=publish_iteration_report,
    )
