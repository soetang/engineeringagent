"""Loop runtime iteration pipeline helpers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    CompletionCommitOutcome,
    FeatureIterationInputs,
    GatePhaseOutcome,
    InitialFeatureLoadOutcome,
    IterationOutcome,
    IterationTelemetryInputs,
    PostImplementFeatureOutcome,
    VerificationPhaseOutcome,
)
from .phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    VerificationPhaseDependencies,
)


class IterationPipelineDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluate_initial_feature_load: Callable[[Path, Path], InitialFeatureLoadOutcome]
    ready_for_active_iteration: Callable[[str, dict[str, Any] | None, bool], bool]
    touch_active_feature_for_iteration: Callable[[dict[str, Any], Path], None]
    run_implement_step: Callable[
        [
            Path,
            dict[str, Any],
            Path,
            str | None,
            str | None,
            bool,
            str | None,
            bool,
        ],
        tuple[bool, str | None, str],
    ]
    refresh_feature_after_implement: Callable[
        [Path, Path, bool], PostImplementFeatureOutcome
    ]
    should_archive_selected_feature: Callable[[str, dict[str, Any] | None, bool], bool]
    archive_completed_feature: Callable[
        [Path, Path], tuple[bool, Path | None, str | None]
    ]
    run_gate_phase: Callable[
        [FeatureIterationInputs, Path, bool, Path | None, GatePhaseDependencies],
        GatePhaseOutcome,
    ]
    gate_phase_dependencies: GatePhaseDependencies
    run_verification_phase: Callable[
        [FeatureIterationInputs, list[str], VerificationPhaseDependencies],
        VerificationPhaseOutcome,
    ]
    verification_phase_dependencies: VerificationPhaseDependencies
    run_completion_commit_phase: Callable[
        [
            FeatureIterationInputs,
            dict[str, Any] | None,
            bool,
            Path | None,
            CompletionPhaseDependencies,
        ],
        CompletionCommitOutcome,
    ]
    completion_phase_dependencies: CompletionPhaseDependencies
    write_iteration_telemetry: Callable[..., str]
    git_head_resolver: Callable[[Path], str | None]
    print_summary: Callable[
        [
            str | None,
            str,
            str | None,
            int | None,
            str,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
        ],
        None,
    ]


class _PipelineState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failed_gate: str | None = None
    result: str = "passed"
    completed: bool = False
    next_action: str = "retry_same_feature"
    next_hook_feedback: str | None = None
    implement_status: str = "not_run"
    gate_status: str = "not_run"
    verification_status: str = "not_run"
    verification_failed_command: str | None = None
    implement_output: str = ""
    gate_output: str = ""
    verification_output: str = ""
    completion_commit_succeeded: bool = False
    archived_path: Path | None = None
    archived_in_iteration: bool = False
    selected_started_active: bool = False
    verification_commands: list[str] = Field(default_factory=list)


def _selected_subtask_verification_commands(
    feature: dict[str, Any] | None,
) -> list[str]:
    if feature is None:
        return []
    subtasks = feature.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        return []

    prioritized_statuses = ("in_progress", "backlog")
    for target_status in prioritized_statuses:
        matching_subtasks = [
            subtask
            for subtask in subtasks
            if isinstance(subtask, dict) and subtask.get("status") == target_status
        ]
        if not matching_subtasks:
            continue

        selected_subtask = sorted(
            matching_subtasks,
            key=lambda subtask: int(subtask.get("order", 1_000_000)),
        )[0]
        verification = selected_subtask.get("verification")
        if not isinstance(verification, list):
            return []
        return [str(command) for command in verification]
    return []


def _apply_initial_load_result(
    state: _PipelineState,
    initial_result: str,
    failed_gate: str | None,
    hook_feedback: str | None,
) -> None:
    if initial_result != "failed":
        return
    state.result = initial_result
    state.failed_gate = failed_gate
    state.next_hook_feedback = hook_feedback


def _run_implement_phase_if_ready(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    feature: dict[str, Any] | None,
    loaded_from_archive: bool,
) -> None:
    if not dependencies.ready_for_active_iteration(
        state.result, feature, loaded_from_archive
    ):
        return

    assert feature is not None
    state.selected_started_active = True
    dependencies.touch_active_feature_for_iteration(
        feature, iteration_inputs.feature_path
    )
    state.verification_commands = _selected_subtask_verification_commands(feature)
    state.implement_status = "skipped" if iteration_inputs.skip_implement else "passed"
    ok, implement_failed_gate, state.implement_output = dependencies.run_implement_step(
        iteration_inputs.project_root,
        feature,
        iteration_inputs.feature_path,
        iteration_inputs.implement_command,
        iteration_inputs.opencode_prompt,
        iteration_inputs.skip_implement,
        iteration_inputs.hook_feedback,
        iteration_inputs.verbose_output,
    )
    if ok:
        return
    state.result = "failed"
    state.failed_gate = implement_failed_gate
    state.implement_status = f"failed:{implement_failed_gate or 'unknown'}"


def _run_verification_phase_if_passed(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
) -> None:
    if state.result != "passed":
        return

    verification_phase = dependencies.run_verification_phase(
        iteration_inputs,
        state.verification_commands,
        dependencies.verification_phase_dependencies,
    )
    state.verification_output = verification_phase.verification_output
    state.verification_status = verification_phase.verification_status
    state.verification_failed_command = verification_phase.verification_failed_command
    if verification_phase.result != "failed":
        return
    state.result = "failed"
    state.next_hook_feedback = verification_phase.hook_feedback


def _refresh_feature_after_implement_if_ready(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    feature: dict[str, Any] | None,
    loaded_from_archive: bool,
) -> tuple[dict[str, Any] | None, bool]:
    if not dependencies.ready_for_active_iteration(
        state.result, feature, loaded_from_archive
    ):
        return feature, loaded_from_archive

    assert feature is not None
    post_refresh = dependencies.refresh_feature_after_implement(
        iteration_inputs.project_root,
        iteration_inputs.feature_path,
        state.selected_started_active,
    )
    state.archived_in_iteration = post_refresh.archived_in_iteration
    state.archived_path = post_refresh.archived_path
    if post_refresh.result == "failed":
        state.result = post_refresh.result
        state.failed_gate = post_refresh.failed_gate
        state.next_hook_feedback = post_refresh.hook_feedback
        return post_refresh.feature, post_refresh.loaded_from_archive

    if post_refresh.feature is not None and not post_refresh.loaded_from_archive:
        dependencies.touch_active_feature_for_iteration(
            post_refresh.feature,
            iteration_inputs.feature_path,
        )
    return post_refresh.feature, post_refresh.loaded_from_archive


def _archive_selected_feature_if_needed(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    post_feature: dict[str, Any] | None,
    loaded_post_from_archive: bool,
) -> None:
    should_archive = dependencies.should_archive_selected_feature(
        state.result,
        post_feature,
        loaded_post_from_archive,
    )
    if not should_archive:
        return

    archived_ok, state.archived_path, archive_error = (
        dependencies.archive_completed_feature(
            iteration_inputs.project_root,
            iteration_inputs.feature_path,
        )
    )
    if archived_ok:
        state.archived_in_iteration = True
        return
    state.result = "failed"
    state.failed_gate = "feature_archive"
    state.next_hook_feedback = archive_error


def _run_gate_phase_if_passed(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    gates_path: Path,
) -> None:
    if state.result != "passed":
        return

    gate_phase = dependencies.run_gate_phase(
        iteration_inputs,
        gates_path,
        state.archived_in_iteration,
        state.archived_path,
        dependencies.gate_phase_dependencies,
    )
    state.gate_output = gate_phase.gate_output
    state.gate_status = gate_phase.gate_status
    if gate_phase.result != "failed":
        return
    state.result = gate_phase.result
    state.failed_gate = gate_phase.failed_gate
    state.next_hook_feedback = gate_phase.hook_feedback


def _run_completion_phase_if_needed(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    post_feature: dict[str, Any] | None,
) -> None:
    if state.result != "passed" or not state.archived_in_iteration:
        return

    completion_phase = dependencies.run_completion_commit_phase(
        iteration_inputs,
        post_feature,
        state.archived_in_iteration,
        state.archived_path,
        dependencies.completion_phase_dependencies,
    )
    state.result = completion_phase.result
    state.failed_gate = completion_phase.failed_gate
    state.next_hook_feedback = completion_phase.hook_feedback
    state.next_action = completion_phase.next_action
    state.completed = completion_phase.completed
    state.completion_commit_succeeded = completion_phase.completion_commit_succeeded


def run_feature_iteration_pipeline(
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
) -> IterationOutcome:
    """Execute one feature iteration while preserving facade seam behavior."""
    gates_path = iteration_inputs.project_root / "harness" / "gates.yaml"
    started = time.time()
    state = _PipelineState()

    initial_load = dependencies.evaluate_initial_feature_load(
        iteration_inputs.project_root,
        iteration_inputs.feature_path,
    )
    feature = initial_load.feature
    loaded_from_archive = initial_load.loaded_from_archive
    feature_id = str(feature.get("id", "")) if feature else ""
    _apply_initial_load_result(
        state,
        initial_load.result,
        initial_load.failed_gate,
        initial_load.hook_feedback,
    )
    _run_implement_phase_if_ready(
        state,
        iteration_inputs,
        dependencies,
        feature,
        loaded_from_archive,
    )
    _run_verification_phase_if_passed(state, iteration_inputs, dependencies)
    post_feature, loaded_post_from_archive = _refresh_feature_after_implement_if_ready(
        state,
        iteration_inputs,
        dependencies,
        feature,
        loaded_from_archive,
    )
    _archive_selected_feature_if_needed(
        state,
        iteration_inputs,
        dependencies,
        post_feature,
        loaded_post_from_archive,
    )
    _run_gate_phase_if_passed(state, iteration_inputs, dependencies, gates_path)
    _run_completion_phase_if_needed(state, iteration_inputs, dependencies, post_feature)

    if state.result == "passed" and not state.completion_commit_succeeded:
        state.completed = False
        state.next_action = "retry_same_feature"

    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=started,
        feature_id=feature_id,
        result=state.result,
        failed_gate=state.failed_gate,
        next_action=state.next_action,
        implement_status=state.implement_status,
        gate_status=state.gate_status,
        verification_status=state.verification_status,
        verification_failed_command=state.verification_failed_command,
        implement_output=state.implement_output,
        gate_output=state.gate_output,
        verification_output=state.verification_output,
        hook_feedback=state.next_hook_feedback,
    )
    feature_progress_log_reference = dependencies.write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=dependencies.git_head_resolver,
    )
    implement_step = (
        "skip_implement=true (gates-only mode)"
        if iteration_inputs.skip_implement
        else (iteration_inputs.implement_command or "default opencode implement step")
    )
    archived_selection_path = (
        str(state.archived_path)
        if loaded_post_from_archive and state.archived_path is not None
        else None
    )
    dependencies.print_summary(
        feature_id,
        state.result,
        state.failed_gate,
        iteration_inputs.attempt,
        state.next_action,
        str(iteration_inputs.feature_path),
        implement_step,
        feature_progress_log_reference if state.result != "passed" else None,
        archived_selection_path,
        state.verification_status,
        state.verification_failed_command,
    )
    if state.result != "passed":
        print(f"Detailed log: {feature_progress_log_reference}")
    return IterationOutcome(
        completed=state.completed,
        result=state.result,
        failed_gate=state.failed_gate,
        next_action=state.next_action,
        hook_feedback=state.next_hook_feedback,
        log_path=feature_progress_log_reference,
        verification_status=state.verification_status,
        verification_failed_command=state.verification_failed_command,
    )
