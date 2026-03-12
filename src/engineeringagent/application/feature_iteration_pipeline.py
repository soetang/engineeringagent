"""Application-owned feature iteration pipeline helpers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from engineeringagent.domain.audit import ImplementProgressEnvelope
from engineeringagent.domain.shared import utc_iso_from_epoch_sec
from engineeringagent.domain.specification import (
    current_progress_unit,
    done_transition_verification_commands,
    feature_progress_reference,
    progress_status_snapshot,
)
from engineeringagent.specs import feature_progress_kind

from .feature_iteration_contracts import (
    CommandTiming,
    CompletionCommitOutcome,
    FeatureIterationInputs,
    GatePhaseOutcome,
    ImplementStepResult,
    InitialFeatureLoadOutcome,
    IterationReport,
    IterationTelemetryInputs,
    PhaseTiming,
    PostImplementFeatureOutcome,
    ReviewerPhaseOutcome,
    VerificationPhaseOutcome,
)


def _default_describe_action(project_root: Path, action: str, structured: bool) -> str:
    """Return a stable fallback action label for injected runtime telemetry."""

    del project_root
    suffix = " --structured" if structured else ""
    return f"engineeringagent {action}{suffix}"


class IterationPipelineDependencies(BaseModel):
    """Injectable dependencies for the iteration pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluate_initial_feature_load: Callable[[Path], InitialFeatureLoadOutcome]
    describe_action: Callable[..., str] = _default_describe_action
    ready_for_active_iteration: Callable[[str, dict[str, Any] | None], bool]
    touch_active_feature_for_iteration: Callable[[dict[str, Any], Path], None]
    run_implement_step: Callable[
        [
            Path,
            dict[str, Any],
            Path,
            str | None,
            bool,
        ],
        ImplementStepResult,
    ]
    refresh_feature_after_implement: Callable[[Path, Path], PostImplementFeatureOutcome]
    should_archive_selected_feature: Callable[[str, dict[str, Any] | None], bool]
    archive_completed_feature: Callable[
        [Path, Path], tuple[bool, Path | None, str | None]
    ]
    run_gate_phase: Callable[
        [FeatureIterationInputs, bool, Path | None, Any],
        GatePhaseOutcome,
    ]
    gate_phase_dependencies: Any
    run_verification_phase: Callable[
        [FeatureIterationInputs, list[str]],
        VerificationPhaseOutcome,
    ]
    run_reviewer_phase: Callable[
        [
            FeatureIterationInputs,
            dict[str, Any] | None,
            bool,
            Path | None,
            Any,
        ],
        ReviewerPhaseOutcome,
    ]
    reviewer_phase_dependencies: Any
    run_completion_commit_phase: Callable[
        [
            FeatureIterationInputs,
            dict[str, Any] | None,
            bool,
            Path | None,
            Any,
        ],
        CompletionCommitOutcome,
    ]
    completion_phase_dependencies: Any


class _PipelineState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failed_gate: str | None = None
    result: str = "passed"
    completed: bool = False
    next_action: str = "retry_same_feature"
    next_feedback: str | None = None
    implement_status: str = "not_run"
    gate_status: str = "not_run"
    verification_status: str = "not_run"
    verification_failed: bool = False
    verification_failed_command: str | None = None
    reviewer_status: str = "not_run"
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None
    implement_output: str = ""
    implement_handoff_envelope: ImplementProgressEnvelope | None = None
    implement_handoff_used_fallback: bool = False
    gate_output: str = ""
    verification_output: str = ""
    reviewer_output: str = ""
    reviewer_feedback_forwarded: str | None = None
    completion_commit_succeeded: bool = False
    completion_output: str = ""
    command_timings: list[CommandTiming] = Field(default_factory=list)
    archived_path: Path | None = None
    archived_in_iteration: bool = False
    selected_started_active: bool = False
    verification_commands: list[str] = Field(default_factory=list)
    pre_implement_progress_statuses: dict[str, str] = Field(default_factory=dict)
    progress_kind: str | None = None
    progress_id: str | None = None
    progress_title: str | None = None


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


def _record_implement_timing(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    started_epoch_sec: int,
    ended_epoch_sec: int,
) -> None:
    if not state.selected_started_active:
        return

    duration_sec = max(0, ended_epoch_sec - started_epoch_sec)
    state.command_timings.append(
        CommandTiming(
            phase="implement",
            command=dependencies.describe_action(
                iteration_inputs.project_root,
                action="implement",
                structured=False,
            ),
            started_at=utc_iso_from_epoch_sec(started_epoch_sec),
            ended_at=utc_iso_from_epoch_sec(ended_epoch_sec),
            duration_sec=duration_sec,
        )
    )


def _apply_initial_load_result(
    state: _PipelineState,
    initial_result: str,
    failed_gate: str | None,
    feedback: str | None,
) -> None:
    if initial_result != "failed":
        return
    state.result = initial_result
    state.failed_gate = failed_gate
    state.next_feedback = feedback


def _run_implement_phase_if_ready(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    feature: dict[str, Any] | None,
) -> None:
    if not dependencies.ready_for_active_iteration(
        state.result,
        feature,
    ):
        return

    assert feature is not None
    state.pre_implement_progress_statuses = progress_status_snapshot(
        iteration_inputs.feature_path,
        feature,
    )
    state.selected_started_active = True
    dependencies.touch_active_feature_for_iteration(
        feature, iteration_inputs.feature_path
    )
    state.implement_status = "passed"
    (
        ok,
        implement_failed_gate,
        state.implement_output,
        state.implement_handoff_envelope,
        state.implement_handoff_used_fallback,
    ) = dependencies.run_implement_step(
        iteration_inputs.project_root,
        feature,
        iteration_inputs.feature_path,
        iteration_inputs.feedback,
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

    verification_feature_path = _resolve_progress_feature_path(
        iteration_inputs,
        state,
    )
    state.verification_commands = done_transition_verification_commands(
        state.pre_implement_progress_statuses,
        verification_feature_path,
        post_feature,
    )

    verification_phase = dependencies.run_verification_phase(
        iteration_inputs,
        state.verification_commands,
    )
    state.command_timings.extend(verification_phase.command_timings)
    state.verification_output = verification_phase.verification_output
    state.verification_status = verification_phase.verification_status
    state.verification_failed_command = verification_phase.verification_failed_command
    if verification_phase.result != "failed":
        return
    state.verification_failed = True
    state.result = "failed"
    state.next_feedback = verification_phase.feedback
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
    state.next_feedback = state.verification_output


def _refresh_feature_after_implement_if_ready(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    feature: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not dependencies.ready_for_active_iteration(
        state.result,
        feature,
    ):
        return feature

    assert feature is not None
    post_refresh = dependencies.refresh_feature_after_implement(
        iteration_inputs.project_root,
        iteration_inputs.feature_path,
    )
    state.archived_in_iteration = post_refresh.archived_in_iteration
    state.archived_path = post_refresh.archived_path
    if post_refresh.result == "failed":
        state.result = post_refresh.result
        state.failed_gate = post_refresh.failed_gate
        state.next_feedback = post_refresh.feedback
        return post_refresh.feature

    if post_refresh.feature is not None and not post_refresh.archived_in_iteration:
        dependencies.touch_active_feature_for_iteration(
            post_refresh.feature,
            iteration_inputs.feature_path,
        )
    return post_refresh.feature


def _archive_selected_feature_if_needed(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    post_feature: dict[str, Any] | None,
) -> None:
    if state.archived_in_iteration:
        return

    should_archive = dependencies.should_archive_selected_feature(
        state.result,
        post_feature,
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
    state.next_feedback = archive_error


def _run_gate_phase_if_passed(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    gate_phase_dependencies: Any,
) -> None:
    should_run_gate = state.result == "passed" or state.verification_failed
    if not should_run_gate:
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
    gate_failed = gate_phase.result == "failed"
    if not gate_failed or state.verification_failed:
        # Verification failure remains the primary retry cause for this iteration.
        # Gate checks still execute for deterministic feedback/telemetry.
        return
    state.result = gate_phase.result
    state.failed_gate = gate_phase.failed_gate
    state.next_feedback = gate_phase.feedback


def _run_reviewer_phase_if_passed(
    state: _PipelineState,
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
    post_feature: dict[str, Any] | None,
    reviewer_phase_dependencies: Any,
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
    feedback = reviewer_phase.feedback
    if feedback:
        state.reviewer_feedback_forwarded = feedback
    if reviewer_phase.result != "failed":
        if feedback:
            state.next_feedback = feedback
        return

    if reviewer_phase.archived_rolled_back:
        state.archived_in_iteration = False
        state.archived_path = None
    state.result = reviewer_phase.result
    state.failed_gate = reviewer_phase.failed_gate
    state.next_feedback = feedback


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
    state.next_feedback = completion_phase.feedback
    state.completed = completion_phase.completed
    state.completion_commit_succeeded = completion_phase.completion_commit_succeeded
    state.completion_output = completion_phase.completion_output
    if completion_phase.archived_rolled_back:
        state.archived_in_iteration = False
        state.archived_path = None


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


def _resolve_progress_feature_path(
    iteration_inputs: FeatureIterationInputs,
    state: _PipelineState,
) -> Path:
    """Resolve the spec path that still owns progress metadata after this iteration."""

    if state.archived_in_iteration and state.archived_path is not None:
        return state.archived_path
    return iteration_inputs.feature_path


def run_feature_iteration_pipeline(
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
) -> IterationReport:
    """Execute one feature iteration through explicit runtime dependencies."""
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
            iteration_inputs.feature_path,
        )
        _apply_initial_load_result(
            state,
            initial_load.result,
            initial_load.failed_gate,
            initial_load.feedback,
        )
        return initial_load

    initial_load = _timed_phase(phase_timings, "initial_load", _run_initial_load_phase)
    feature = initial_load.feature
    feature_id = str(feature.get("id", "")) if feature else ""

    def _implement_timing_hook(started_epoch_sec: int, ended_epoch_sec: int) -> None:
        _record_implement_timing(
            state,
            iteration_inputs,
            dependencies,
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
        ),
        timing_hook=_implement_timing_hook,
    )
    post_feature = _refresh_feature_after_implement_if_ready(
        state,
        iteration_inputs,
        dependencies,
        feature,
    )

    _timed_phase(
        phase_timings,
        "archive",
        lambda: _archive_selected_feature_if_needed(
            state,
            iteration_inputs,
            dependencies,
            post_feature,
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
    progress_feature_path = _resolve_progress_feature_path(iteration_inputs, state)
    progress_unit = current_progress_unit(
        progress_feature_path,
        post_feature if post_feature is not None else feature,
    )
    if progress_unit is not None:
        state.progress_kind = progress_unit.kind
        state.progress_id = progress_unit.id
        state.progress_title = progress_unit.title
    else:
        resolved_progress_kind = feature_progress_kind(
            progress_feature_path,
            post_feature if post_feature is not None else feature,
        )
        state.progress_kind = resolved_progress_kind
        if resolved_progress_kind == "feature":
            state.progress_id, state.progress_title = feature_progress_reference(
                post_feature if post_feature is not None else feature
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
        progress_kind=state.progress_kind,
        progress_id=state.progress_id,
        progress_title=state.progress_title,
        implement_output=state.implement_output,
        implement_handoff_envelope=state.implement_handoff_envelope,
        implement_handoff_used_fallback=state.implement_handoff_used_fallback,
        gate_output=state.gate_output,
        verification_output=state.verification_output,
        reviewer_output=state.reviewer_output,
        reviewer_feedback_forwarded=state.reviewer_feedback_forwarded,
        feedback=state.next_feedback,
        completion_output=state.completion_output,
    )
    implement_step = dependencies.describe_action(
        iteration_inputs.project_root,
        action="implement",
        structured=False,
    )
    return IterationReport(
        completed=state.completed,
        result=state.result,
        failed_gate=state.failed_gate,
        next_action=state.next_action,
        feedback=state.next_feedback,
        feature_id=feature_id,
        attempt=iteration_inputs.attempt,
        selected_feature_path=str(iteration_inputs.feature_path),
        implement_step=implement_step,
        archived_selection_path=None,
        verification_status=state.verification_status,
        verification_failed_command=state.verification_failed_command,
        reviewer_status=state.reviewer_status,
        reviewer_decision=state.reviewer_decision,
        failed_reviewer_id=state.failed_reviewer_id,
        telemetry_inputs=telemetry_inputs,
    )
