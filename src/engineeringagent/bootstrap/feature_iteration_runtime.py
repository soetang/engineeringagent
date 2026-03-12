"""Bootstrap-owned assembly for feature-iteration runtime dependencies."""

from __future__ import annotations

from types import SimpleNamespace

from engineeringagent.adapters.progress import write_iteration_telemetry
from engineeringagent.application import FeatureIterationRuntimeDependencies
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
from engineeringagent.application import iteration_models
from engineeringagent.bootstrap import runtime_support
from engineeringagent.loop_runtime import feature_state, iteration


def build_feature_iteration_runtime_dependencies() -> (
    FeatureIterationRuntimeDependencies
):
    """Build the default runtime seam bundle for feature iterations."""
    runtime = SimpleNamespace(
        checks=SimpleNamespace(collect_changed_paths=collect_changed_paths),
        support=runtime_support,
        feature_state=feature_state,
        iteration=iteration,
        models=iteration_models,
        phases=SimpleNamespace(
            GatePhaseDependencies=GatePhaseDependencies,
            ReviewerPhaseDependencies=ReviewerPhaseDependencies,
            CompletionPhaseDependencies=CompletionPhaseDependencies,
            run_gate_phase=run_gate_phase,
            run_verification_phase=run_verification_phase,
            run_reviewer_phase=run_reviewer_phase,
            run_completion_commit_phase=run_completion_commit_phase,
        ),
    )
    return FeatureIterationRuntimeDependencies(
        runtime=runtime,
        observer_dependencies_type=DefaultObserverDependencies,
        write_iteration_telemetry_fn=write_iteration_telemetry,
        build_iteration_report_observers_fn=build_default_iteration_report_observers,
        publish_iteration_report_fn=publish_iteration_report,
    )
