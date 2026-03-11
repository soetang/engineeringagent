"""Contracts for feature-iteration execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict


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


class FeatureIterationRuntime(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Legacy runtime collaborators injected by bootstrap for one iteration."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    build_inputs: Callable[..., object]
    build_iteration_dependencies: Callable[..., object]
    run_feature_iteration_pipeline: Callable[..., Any]
    build_gate_phase_dependencies: Callable[..., object]
    build_reviewer_phase_dependencies: Callable[..., object]
    build_completion_phase_dependencies: Callable[..., object]
    build_default_observer_dependencies: Callable[..., object]
    build_default_iteration_report_observers: Callable[..., object]
    publish_iteration_report: Callable[..., Any]
    write_iteration_telemetry: Callable[..., object]
    run_implement_step: object
    git_head_resolver: object
    print_summary: object
    evaluate_initial_feature_load: object
    ready_for_active_iteration: object
    touch_active_feature_for_iteration: object
    refresh_feature_after_implement: object
    should_archive_selected_feature: object
    archive_completed_feature: object
    restore_archived_feature: object
    collect_changed_paths: object
    run_gate_phase: object
    run_verification_phase: object
    run_reviewer_phase: object
    run_completion_commit_phase: object
