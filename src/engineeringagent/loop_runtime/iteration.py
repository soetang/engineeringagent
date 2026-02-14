"""Loop runtime iteration pipeline helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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


@dataclass(frozen=True)
class IterationPipelineDependencies:
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


def run_feature_iteration_pipeline(
    iteration_inputs: FeatureIterationInputs,
    dependencies: IterationPipelineDependencies,
) -> IterationOutcome:
    """Execute one feature iteration while preserving facade seam behavior."""
    gates_path = iteration_inputs.project_root / "harness" / "gates.yaml"
    started = time.time()

    failed_gate: str | None = None
    result = "passed"
    completed = False
    next_action = "retry_same_feature"
    next_hook_feedback: str | None = None
    implement_status = "not_run"
    gate_status = "not_run"
    verification_status = "not_run"
    verification_failed_command: str | None = None
    implement_output = ""
    gate_output = ""
    verification_output = ""
    completion_commit_succeeded = False
    archived_path: Path | None = None
    archived_in_iteration = False
    selected_started_active = False
    verification_commands: list[str] = []

    initial_load = dependencies.evaluate_initial_feature_load(
        iteration_inputs.project_root,
        iteration_inputs.feature_path,
    )
    feature = initial_load.feature
    loaded_from_archive = initial_load.loaded_from_archive
    feature_id = str(feature.get("id", "")) if feature else ""
    if initial_load.result == "failed":
        result = initial_load.result
        failed_gate = initial_load.failed_gate
        next_hook_feedback = initial_load.hook_feedback

    if dependencies.ready_for_active_iteration(result, feature, loaded_from_archive):
        assert feature is not None
        selected_started_active = True
        dependencies.touch_active_feature_for_iteration(
            feature, iteration_inputs.feature_path
        )

    if dependencies.ready_for_active_iteration(result, feature, loaded_from_archive):
        assert feature is not None
        verification_commands = _selected_subtask_verification_commands(feature)
        implement_status = "skipped" if iteration_inputs.skip_implement else "passed"
        ok, implement_failed_gate, implement_output = dependencies.run_implement_step(
            iteration_inputs.project_root,
            feature,
            iteration_inputs.feature_path,
            iteration_inputs.implement_command,
            iteration_inputs.opencode_prompt,
            iteration_inputs.skip_implement,
            iteration_inputs.hook_feedback,
            iteration_inputs.verbose_output,
        )
        if not ok:
            result = "failed"
            failed_gate = implement_failed_gate
            implement_status = f"failed:{implement_failed_gate or 'unknown'}"

    if result == "passed":
        verification_phase = dependencies.run_verification_phase(
            iteration_inputs,
            verification_commands,
            dependencies.verification_phase_dependencies,
        )
        verification_output = verification_phase.verification_output
        verification_status = verification_phase.verification_status
        verification_failed_command = verification_phase.verification_failed_command
        if verification_phase.result == "failed":
            result = "failed"
            next_hook_feedback = verification_phase.hook_feedback

    post_feature = feature
    loaded_post_from_archive = loaded_from_archive
    if dependencies.ready_for_active_iteration(result, feature, loaded_from_archive):
        assert feature is not None
        post_refresh = dependencies.refresh_feature_after_implement(
            iteration_inputs.project_root,
            iteration_inputs.feature_path,
            selected_started_active,
        )
        post_feature = post_refresh.feature
        loaded_post_from_archive = post_refresh.loaded_from_archive
        archived_in_iteration = post_refresh.archived_in_iteration
        archived_path = post_refresh.archived_path
        if post_refresh.result == "failed":
            result = post_refresh.result
            failed_gate = post_refresh.failed_gate
            next_hook_feedback = post_refresh.hook_feedback
        elif post_feature is not None and not loaded_post_from_archive:
            dependencies.touch_active_feature_for_iteration(
                post_feature,
                iteration_inputs.feature_path,
            )

    if dependencies.should_archive_selected_feature(
        result,
        post_feature,
        loaded_post_from_archive,
    ):
        archived_ok, archived_path, archive_error = (
            dependencies.archive_completed_feature(
                iteration_inputs.project_root,
                iteration_inputs.feature_path,
            )
        )
        if not archived_ok:
            result = "failed"
            failed_gate = "feature_archive"
            next_hook_feedback = archive_error
        else:
            archived_in_iteration = True

    if result == "passed":
        gate_phase = dependencies.run_gate_phase(
            iteration_inputs,
            gates_path,
            archived_in_iteration,
            archived_path,
            dependencies.gate_phase_dependencies,
        )
        gate_output = gate_phase.gate_output
        if gate_phase.result == "failed":
            result = gate_phase.result
            failed_gate = gate_phase.failed_gate
            gate_status = gate_phase.gate_status
            next_hook_feedback = gate_phase.hook_feedback
        else:
            gate_status = gate_phase.gate_status

    if result == "passed" and archived_in_iteration:
        completion_phase = dependencies.run_completion_commit_phase(
            iteration_inputs,
            post_feature,
            archived_in_iteration,
            archived_path,
            dependencies.completion_phase_dependencies,
        )
        result = completion_phase.result
        failed_gate = completion_phase.failed_gate
        next_hook_feedback = completion_phase.hook_feedback
        next_action = completion_phase.next_action
        completed = completion_phase.completed
        completion_commit_succeeded = completion_phase.completion_commit_succeeded

    if result == "passed" and not completion_commit_succeeded:
        completed = False
        next_action = "retry_same_feature"

    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=started,
        feature_id=feature_id,
        result=result,
        failed_gate=failed_gate,
        next_action=next_action,
        implement_status=implement_status,
        gate_status=gate_status,
        verification_status=verification_status,
        verification_failed_command=verification_failed_command,
        implement_output=implement_output,
        gate_output=gate_output,
        verification_output=verification_output,
        hook_feedback=next_hook_feedback,
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
        str(archived_path)
        if loaded_post_from_archive and archived_path is not None
        else None
    )
    dependencies.print_summary(
        feature_id,
        result,
        failed_gate,
        iteration_inputs.attempt,
        next_action,
        str(iteration_inputs.feature_path),
        implement_step,
        feature_progress_log_reference if result != "passed" else None,
        archived_selection_path,
        verification_status,
        verification_failed_command,
    )
    if result != "passed":
        print(f"Detailed log: {feature_progress_log_reference}")
    return IterationOutcome(
        completed=completed,
        result=result,
        failed_gate=failed_gate,
        next_action=next_action,
        hook_feedback=next_hook_feedback,
        log_path=feature_progress_log_reference,
        verification_status=verification_status,
        verification_failed_command=verification_failed_command,
    )
