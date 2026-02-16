"""Loop runtime iteration pipeline helpers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    CommandTiming,
    CompletionCommitOutcome,
    FeatureIterationInputs,
    GatePhaseOutcome,
    InitialFeatureLoadOutcome,
    IterationOutcome,
    IterationTelemetryInputs,
    PhaseTiming,
    PostImplementFeatureOutcome,
    ReviewerPhaseOutcome,
    VerificationPhaseOutcome,
)
from .phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    VerificationPhaseDependencies,
)
from .time_format import utc_iso_from_epoch_sec


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
        [FeatureIterationInputs, bool, Path | None, GatePhaseDependencies],
        GatePhaseOutcome,
    ]
    gate_phase_dependencies: GatePhaseDependencies
    run_verification_phase: Callable[
        [FeatureIterationInputs, list[str], VerificationPhaseDependencies],
        VerificationPhaseOutcome,
    ]
    verification_phase_dependencies: VerificationPhaseDependencies
    run_reviewer_phase: Callable[
        [
            FeatureIterationInputs,
            dict[str, Any] | None,
            bool,
            Path | None,
            ReviewerPhaseDependencies,
        ],
        ReviewerPhaseOutcome,
    ]
    reviewer_phase_dependencies: ReviewerPhaseDependencies
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
    reviewer_status: str = "not_run"
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None
    implement_output: str = ""
    gate_output: str = ""
    verification_output: str = ""
    reviewer_output: str = ""
    reviewer_feedback_forwarded: str | None = None
    completion_commit_succeeded: bool = False
    command_timings: list[CommandTiming] = Field(default_factory=list)
    archived_path: Path | None = None
    archived_in_iteration: bool = False
    selected_started_active: bool = False
    verification_commands: list[str] = Field(default_factory=list)
    pre_implement_subtask_statuses: dict[str, str] = Field(default_factory=dict)


T = TypeVar("T")


def _timed_phase(
    phase_timings: list[PhaseTiming],
    phase: str,
    fn: Callable[[], T],
    *,
    timing_hook: Callable[[int, int], None] | None = None,
) -> T:
    started_epoch_sec = int(time.time())
    result = fn()
    ended_epoch_sec = max(started_epoch_sec, int(time.time()))
    duration_sec = ended_epoch_sec - started_epoch_sec
    phase_timings.append(
        PhaseTiming(
            phase=phase,
            started_at=utc_iso_from_epoch_sec(started_epoch_sec),
            ended_at=utc_iso_from_epoch_sec(ended_epoch_sec),
            duration_sec=duration_sec,
        )
    )
    if timing_hook is not None:
        timing_hook(started_epoch_sec, ended_epoch_sec)
    return result


def _default_implement_step_label() -> str:
    from engineeringagent.opencode.client import DEFAULT_OPENCODE_AGENT

    return f"opencode run --agent {DEFAULT_OPENCODE_AGENT}"


def _record_implement_timing(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    started_epoch_sec: int,
    ended_epoch_sec: int,
) -> None:
    if not state.selected_started_active:
        return

    duration_sec = max(0, ended_epoch_sec - started_epoch_sec)
    state.command_timings.append(
        CommandTiming(
            phase="implement",
            command=_default_implement_step_label(),
            started_at=utc_iso_from_epoch_sec(started_epoch_sec),
            ended_at=utc_iso_from_epoch_sec(ended_epoch_sec),
            duration_sec=duration_sec,
        )
    )


def _subtask_status_snapshot(
    feature: dict[str, Any] | None,
) -> dict[str, str]:
    status_by_id: dict[str, str] = {}
    for subtask in _iter_subtasks(feature):
        subtask_id = subtask.get("id")
        subtask_status = subtask.get("status")
        if not isinstance(subtask_id, str) or not subtask_id:
            continue
        if not isinstance(subtask_status, str):
            continue
        status_by_id.setdefault(subtask_id, subtask_status)
    return status_by_id


def _done_transition_verification_commands(
    previous_status_by_subtask_id: dict[str, str],
    post_feature: dict[str, Any] | None,
) -> list[str]:
    commands: list[str] = []
    for subtask in _iter_unique_subtasks_by_id(post_feature):
        subtask_id = subtask.get("id")
        assert isinstance(subtask_id, str)
        previous_status = previous_status_by_subtask_id.get(subtask_id)
        if not _transitioned_to_done(previous_status, subtask.get("status")):
            continue
        verification = subtask.get("verification")
        if not isinstance(verification, list):
            continue
        commands.extend(_iter_verification_commands(verification))
    return commands


def _transitioned_to_done(previous_status: str | None, current_status: Any) -> bool:
    return (
        previous_status is not None
        and previous_status != "done"
        and current_status == "done"
    )


def _iter_unique_subtasks_by_id(
    feature: dict[str, Any] | None,
) -> Iterable[dict[str, Any]]:
    seen_subtask_ids: set[str] = set()
    for subtask in _iter_subtasks(feature):
        subtask_id = subtask.get("id")
        if not isinstance(subtask_id, str) or not subtask_id:
            continue
        if subtask_id in seen_subtask_ids:
            continue
        seen_subtask_ids.add(subtask_id)
        yield subtask


def _iter_subtasks(feature: dict[str, Any] | None) -> Iterable[dict[str, Any]]:
    if feature is None:
        return ()
    subtasks = feature.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        return ()
    return (subtask for subtask in subtasks if isinstance(subtask, dict))


def _iter_verification_commands(verification: list[Any]) -> Iterable[str]:
    for command in verification:
        if not isinstance(command, str):
            continue
        normalized_command = command.strip()
        if normalized_command:
            yield normalized_command


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
    state.pre_implement_subtask_statuses = _subtask_status_snapshot(feature)
    state.selected_started_active = True
    dependencies.touch_active_feature_for_iteration(
        feature, iteration_inputs.feature_path
    )
    state.implement_status = "passed"
    ok, implement_failed_gate, state.implement_output = dependencies.run_implement_step(
        iteration_inputs.project_root,
        feature,
        iteration_inputs.feature_path,
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
    post_feature: dict[str, Any] | None,
) -> None:
    if state.result != "passed":
        return

    state.verification_commands = _done_transition_verification_commands(
        state.pre_implement_subtask_statuses,
        post_feature,
    )

    verification_phase = dependencies.run_verification_phase(
        iteration_inputs,
        state.verification_commands,
        dependencies.verification_phase_dependencies,
    )
    state.command_timings.extend(verification_phase.command_timings)
    state.verification_output = verification_phase.verification_output
    state.verification_status = verification_phase.verification_status
    state.verification_failed_command = verification_phase.verification_failed_command
    if verification_phase.result != "failed":
        return
    state.result = "failed"
    state.next_hook_feedback = verification_phase.hook_feedback
    _rollback_archived_feature_after_verification_failure(
        state,
        iteration_inputs,
        dependencies,
    )


def _rollback_archived_feature_after_verification_failure(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
) -> None:
    if not state.archived_in_iteration or state.archived_path is None:
        return

    restored_ok, restore_error = (
        dependencies.gate_phase_dependencies.restore_archived_feature(
            state.archived_path,
            iteration_inputs.feature_path,
        )
    )
    if restored_ok:
        state.archived_in_iteration = False
        state.archived_path = None
        return

    rollback_output = f"\narchive rollback failed: {restore_error}"
    state.verification_output = f"{state.verification_output}{rollback_output}".strip()
    state.next_hook_feedback = state.verification_output


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
    gate_phase_dependencies: GatePhaseDependencies,
) -> None:
    if state.result != "passed":
        return

    gate_phase = dependencies.run_gate_phase(
        iteration_inputs,
        state.archived_in_iteration,
        state.archived_path,
        gate_phase_dependencies,
    )
    state.gate_output = gate_phase.gate_output
    state.gate_status = gate_phase.gate_status
    state.command_timings.extend(gate_phase.command_timings)
    if gate_phase.result != "failed":
        return
    state.result = gate_phase.result
    state.failed_gate = gate_phase.failed_gate
    state.next_hook_feedback = gate_phase.hook_feedback


def _run_reviewer_phase_if_passed(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    post_feature: dict[str, Any] | None,
    reviewer_phase_dependencies: ReviewerPhaseDependencies,
) -> None:
    if state.result != "passed":
        return

    reviewer_phase = dependencies.run_reviewer_phase(
        iteration_inputs,
        post_feature,
        state.archived_in_iteration,
        state.archived_path,
        reviewer_phase_dependencies,
    )
    state.reviewer_status = reviewer_phase.reviewer_status
    state.reviewer_decision = reviewer_phase.reviewer_decision
    state.failed_reviewer_id = reviewer_phase.failed_reviewer_id
    state.reviewer_output = reviewer_phase.reviewer_output
    state.command_timings.extend(reviewer_phase.command_timings)
    if reviewer_phase.hook_feedback:
        state.reviewer_feedback_forwarded = reviewer_phase.hook_feedback
    if reviewer_phase.result != "failed":
        if reviewer_phase.hook_feedback:
            state.next_hook_feedback = reviewer_phase.hook_feedback
        return

    state.result = reviewer_phase.result
    state.failed_gate = reviewer_phase.failed_gate
    state.next_hook_feedback = reviewer_phase.hook_feedback


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
    state.completed = completion_phase.completed
    state.completion_commit_succeeded = completion_phase.completion_commit_succeeded


def _derive_next_action(*, result: str, completion_commit_succeeded: bool) -> str:
    """Derive next_action deterministically from final iteration state.

    This mapping is intentionally narrow so telemetry/output cleanly distinguishes:
    - passed continuation vs failed retry vs select-next after completion.
    """

    if result == "failed":
        return "retry_same_feature"
    if completion_commit_succeeded:
        return "select_next_feature"
    return "continue_same_feature"


def run_feature_iteration_pipeline(
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
) -> IterationOutcome:
    """Execute one feature iteration while preserving facade seam behavior."""
    changed_paths_cached: Any | None = None
    changed_paths_captured = False

    def _collect_changed_paths_once(project_root: Path) -> Any:
        nonlocal changed_paths_cached, changed_paths_captured
        if changed_paths_captured:
            return changed_paths_cached
        changed_paths_cached = (
            dependencies.gate_phase_dependencies.collect_changed_paths(project_root)
        )
        changed_paths_captured = True
        return changed_paths_cached

    gate_phase_dependencies = dependencies.gate_phase_dependencies.model_copy(
        update={"collect_changed_paths": _collect_changed_paths_once}
    )
    reviewer_phase_dependencies = dependencies.reviewer_phase_dependencies.model_copy(
        update={"collect_changed_paths": _collect_changed_paths_once}
    )

    started = time.time()
    state = _PipelineState()
    phase_timings: list[PhaseTiming] = []

    def _run_initial_load_phase() -> InitialFeatureLoadOutcome:
        initial_load = dependencies.evaluate_initial_feature_load(
            iteration_inputs.project_root,
            iteration_inputs.feature_path,
        )
        _apply_initial_load_result(
            state,
            initial_load.result,
            initial_load.failed_gate,
            initial_load.hook_feedback,
        )
        return initial_load

    initial_load = _timed_phase(phase_timings, "initial_load", _run_initial_load_phase)
    feature = initial_load.feature
    loaded_from_archive = initial_load.loaded_from_archive
    feature_id = str(feature.get("id", "")) if feature else ""

    def _implement_timing_hook(started_epoch_sec: int, ended_epoch_sec: int) -> None:
        _record_implement_timing(
            state,
            iteration_inputs,
            started_epoch_sec,
            ended_epoch_sec,
        )

    _timed_phase(
        phase_timings,
        "implement",
        lambda: _run_implement_phase_if_ready(
            state,
            iteration_inputs,
            dependencies,
            feature,
            loaded_from_archive,
        ),
        timing_hook=_implement_timing_hook,
    )
    post_feature, loaded_post_from_archive = _refresh_feature_after_implement_if_ready(
        state,
        iteration_inputs,
        dependencies,
        feature,
        loaded_from_archive,
    )

    _timed_phase(
        phase_timings,
        "archive",
        lambda: _archive_selected_feature_if_needed(
            state,
            iteration_inputs,
            dependencies,
            post_feature,
            loaded_post_from_archive,
        ),
    )
    _timed_phase(
        phase_timings,
        "verification",
        lambda: _run_verification_phase_if_passed(
            state,
            iteration_inputs,
            dependencies,
            post_feature,
        ),
    )
    _timed_phase(
        phase_timings,
        "gates",
        lambda: _run_gate_phase_if_passed(
            state,
            iteration_inputs,
            dependencies,
            gate_phase_dependencies,
        ),
    )
    _timed_phase(
        phase_timings,
        "reviewers",
        lambda: _run_reviewer_phase_if_passed(
            state,
            iteration_inputs,
            dependencies,
            post_feature,
            reviewer_phase_dependencies,
        ),
    )
    _timed_phase(
        phase_timings,
        "completion_commit",
        lambda: _run_completion_phase_if_needed(
            state,
            iteration_inputs,
            dependencies,
            post_feature,
        ),
    )

    if state.result != "passed":
        state.completed = False
    state.next_action = _derive_next_action(
        result=state.result,
        completion_commit_succeeded=state.completion_commit_succeeded,
    )

    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=started,
        phase_timings=phase_timings,
        command_timings=state.command_timings,
        feature_id=feature_id,
        result=state.result,
        failed_gate=state.failed_gate,
        next_action=state.next_action,
        implement_status=state.implement_status,
        gate_status=state.gate_status,
        verification_status=state.verification_status,
        verification_failed_command=state.verification_failed_command,
        reviewer_status=state.reviewer_status,
        reviewer_decision=state.reviewer_decision,
        failed_reviewer_id=state.failed_reviewer_id,
        implement_output=state.implement_output,
        gate_output=state.gate_output,
        verification_output=state.verification_output,
        reviewer_output=state.reviewer_output,
        reviewer_feedback_forwarded=state.reviewer_feedback_forwarded,
        hook_feedback=state.next_hook_feedback,
    )
    feature_progress_log_reference = dependencies.write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=dependencies.git_head_resolver,
    )
    implement_step = _default_implement_step_label()
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
        state.reviewer_status,
        state.reviewer_decision,
        state.failed_reviewer_id,
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
        reviewer_status=state.reviewer_status,
        reviewer_decision=state.reviewer_decision,
        failed_reviewer_id=state.failed_reviewer_id,
    )
