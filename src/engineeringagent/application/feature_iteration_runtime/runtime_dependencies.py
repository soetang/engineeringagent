"""Feature-iteration service wiring contracts owned by the subpackage."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from engineeringagent.ports import Clock, ProgressJournal, VersionControlGateway

from .contracts import IterationReport
from .pipeline import IterationPipelineDependencies


class FeatureIterationRuntimeDependencies(BaseModel):
    """Application-owned runtime seams for feature-iteration execution."""

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
    run_feature_iteration_pipeline: Callable[..., Any]
    run_gate_phase: Callable[..., Any]
    build_gate_phase_dependencies: Callable[..., Any]
    run_verification_phase: Callable[..., Any]
    run_reviewer_phase: Callable[..., Any]
    build_reviewer_phase_dependencies: Callable[..., Any]
    run_completion_commit_phase: Callable[..., Any]
    build_completion_phase_dependencies: Callable[..., Any]
    git_head_short: Any
    print_summary: Callable[[Any], None]
    observer_dependencies_type: Any
    write_iteration_telemetry: Callable[..., str]
    build_iteration_pipeline_dependencies: Callable[
        ["FeatureIterationRuntimeDependencies", VersionControlGateway],
        IterationPipelineDependencies,
    ]
    build_iteration_report_observers: Callable[
        ["FeatureIterationRuntimeDependencies", ProgressJournal],
        Any,
    ]
    publish_iteration_report: Callable[[IterationReport, Any], Any]
