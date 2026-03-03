"""Loop runtime gate/completion phase helpers."""

from __future__ import annotations

from pathlib import Path
import shlex
import sys
import time
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from ..changed_paths import ChangedPathsResult
from ..checks import (
    ChecksRunResult,
    run_checks,
)
from ..prompt_feedback import (
    format_failed_command_feedback_lines,
    resolve_checks_prompt_feedback,
)
from ..prompts.feedback_envelope import (
    build_command_failure_feedback,
)
from ..process import run_shell_command
from ..specs import HarnessCheckPhase

from .models import (
    CommandTiming,
    CompletionCommitOutcome,
    FeatureIterationInputs,
    GatePhaseOutcome,
    ReviewerPhaseOutcome,
    VerificationPhaseOutcome,
)
from .time_format import utc_iso_from_epoch_sec
from ..feature_commit import feature_completion_commit_subject


class LoopTriggeredChecksRequest(BaseModel):
    """Structured request for loop-triggered checks execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    phase: HarnessCheckPhase
    collect_changed_paths: Callable[..., Any] | None = None
    feature_path: Path | None = None
    run_agent_fn: Callable[..., Any] | None = None
    feedback: str | None = None
    verbose_output: bool = False


def _run_loop_triggered_checks(request: LoopTriggeredChecksRequest) -> ChecksRunResult:
    """Run checks from loop runtime using checks-owned selection policy."""
    return run_checks(
        request.project_root,
        phase=request.phase,
        feature_path=request.feature_path,
        run_agent_fn=request.run_agent_fn,
        feedback=request.feedback,
        verbose_output=request.verbose_output,
        collect_changed_paths=request.collect_changed_paths,
    )


def _append_gate_command_timings(
    invocations: tuple[Any, ...],
    command_timings: list[CommandTiming],
) -> None:
    for invocation in invocations:
        started = invocation.started_epoch_sec
        ended = invocation.ended_epoch_sec
        command_timings.append(
            CommandTiming(
                phase="gates",
                gate=invocation.check_id,
                command=invocation.command,
                started_at=utc_iso_from_epoch_sec(started),
                ended_at=utc_iso_from_epoch_sec(ended),
                duration_sec=ended - started,
            )
        )


def _checks_failure_gate_id(result: ChecksRunResult, *, default: str) -> str:
    """Return a deterministic failed-gate identifier from checks results."""

    return result.failed_check_id or default


def _checks_failure_feedback(result: ChecksRunResult) -> str | None:
    """Return normalized feedback for failed checks results."""

    return resolve_checks_prompt_feedback(result.prompt_feedback)


class GatePhaseDependencies(BaseModel):
    """Injectable dependencies for the gate phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]
    collect_changed_paths: Callable[[Path], ChangedPathsResult]


class CompletionPhaseDependencies(BaseModel):
    """Injectable dependencies for the completion-commit phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    commit_feature_completion: Callable[
        [Path, dict[str, Any]], tuple[bool, str | None, str]
    ]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]


class ReviewerPhaseDependencies(BaseModel):
    """Injectable dependencies for the reviewer phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    collect_changed_paths: Callable[..., Any]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]
    run_agent_fn: Callable[..., Any] | None = None


class GateFailureDetails(BaseModel):
    """Input payload for constructing a gate failure outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    archived_in_iteration: bool
    archived_path: Path | None
    failure_result: ChecksRunResult
    combined_output: str
    command_timings: list[CommandTiming]


def _gate_not_configured_outcome(run_all: bool) -> GatePhaseOutcome:
    if run_all:
        output = "missing harness/checks.yaml (required for --all)"
        return GatePhaseOutcome(
            result="failed",
            failed_gate="checks_config",
            gate_status="failed:checks_config",
            gate_output=output,
            command_timings=[],
            feedback=output,
        )
    return GatePhaseOutcome(
        result="passed",
        failed_gate=None,
        gate_status="not_configured",
        gate_output="",
        command_timings=[],
        feedback=None,
    )


def _run_gate_phase_checks(
    iteration_inputs: FeatureIterationInputs,
    dependencies: GatePhaseDependencies,
    *,
    archived_in_iteration: bool,
) -> tuple[ChecksRunResult, list[str], list[CommandTiming]]:
    outputs: list[str] = []
    command_timings: list[CommandTiming] = []
    gate_phases = (HarnessCheckPhase.ITERATION_END,) if not archived_in_iteration else (
        HarnessCheckPhase.ITERATION_END,
        HarnessCheckPhase.FEATURE_DONE,
    )

    for phase in gate_phases:
        result = _run_loop_triggered_checks(
            LoopTriggeredChecksRequest(
                project_root=iteration_inputs.project_root,
                phase=phase,
                collect_changed_paths=dependencies.collect_changed_paths,
                verbose_output=iteration_inputs.verbose_output,
            )
        )
        _append_gate_command_timings(result.command_invocations, command_timings)
        if result.output:
            outputs.append(result.output)
        if not result.ok:
            break

    return result, outputs, command_timings


def _gate_failure_outcome(
    iteration_inputs: FeatureIterationInputs,
    dependencies: GatePhaseDependencies,
    details: GateFailureDetails,
) -> GatePhaseOutcome:
    failed_gate = _checks_failure_gate_id(details.failure_result, default="checks_config")
    combined_output = details.combined_output
    if details.archived_in_iteration and details.archived_path is not None:
        restored_ok, restore_error = dependencies.restore_archived_feature(
            details.archived_path,
            iteration_inputs.feature_path,
        )
        if not restored_ok:
            rollback_output = f"\narchive rollback failed: {restore_error}"
            combined_output = f"{combined_output}{rollback_output}".strip()

    return GatePhaseOutcome(
        result="failed",
        failed_gate=failed_gate,
        gate_status=f"failed:{failed_gate or 'unknown'}",
        gate_output=combined_output,
        command_timings=details.command_timings,
        feedback=_checks_failure_feedback(details.failure_result),
    )


def run_gate_phase(
    iteration_inputs: FeatureIterationInputs,
    archived_in_iteration: bool,
    archived_path: Path | None,
    dependencies: GatePhaseDependencies,
) -> GatePhaseOutcome:
    """Run post-implement gates and perform archive rollback on failure."""
    checks_path = iteration_inputs.project_root / "harness" / "checks.yaml"
    if not checks_path.exists():
        return _gate_not_configured_outcome(iteration_inputs.run_all)

    last_result, outputs, command_timings = _run_gate_phase_checks(
        iteration_inputs,
        dependencies,
        archived_in_iteration=archived_in_iteration,
    )
    combined_output = "\n".join(part for part in outputs if part).strip()
    if last_result.ok:
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="passed",
            gate_output=combined_output,
            command_timings=command_timings,
            feedback=None,
        )

    return _gate_failure_outcome(
        iteration_inputs,
        dependencies,
        GateFailureDetails(
            archived_in_iteration=archived_in_iteration,
            archived_path=archived_path,
            failure_result=last_result,
            combined_output=combined_output,
            command_timings=command_timings,
        ),
    )


def run_verification_phase(
    iteration_inputs: FeatureIterationInputs,
    verification_commands: list[str],
) -> VerificationPhaseOutcome:
    """Run selected-subtask verification commands for the current iteration."""
    if not verification_commands:
        return VerificationPhaseOutcome(
            result="passed",
            verification_status="not_run",
            verification_failed_command=None,
            verification_output="",
            command_timings=[],
            feedback=None,
        )

    command_outputs: list[str] = []
    command_timings: list[CommandTiming] = []
    for command in verification_commands:
        print(f"Verification step: {command}")
        started_epoch_sec = int(time.time())
        proc = run_shell_command(iteration_inputs.project_root, command)
        ended_epoch_sec = max(started_epoch_sec, int(time.time()))
        if iteration_inputs.verbose_output:
            if proc.stdout:
                print(proc.stdout, end="")
            if proc.stderr:
                print(proc.stderr, end="", file=sys.stderr)
        output = (proc.stdout or "") + (proc.stderr or "")
        command_timings.append(
            CommandTiming(
                phase="verification",
                command=command,
                started_at=utc_iso_from_epoch_sec(started_epoch_sec),
                ended_at=utc_iso_from_epoch_sec(ended_epoch_sec),
                duration_sec=ended_epoch_sec - started_epoch_sec,
            )
        )
        command_output = (
            f"[verification] command={command}\n"
            f"[verification] returncode={proc.returncode}\n"
            f"{output}"
        )
        command_outputs.append(command_output)

        if proc.returncode != 0:
            verification_output = "\n".join(command_outputs)
            message = "\n".join(
                [
                    "Verification command failed.",
                    *format_failed_command_feedback_lines(
                        command=command,
                        return_code=proc.returncode,
                        failure_output=output,
                    ),
                ]
            )
            feedback = build_command_failure_feedback(
                phase="verification",
                gate=None,
                command=command,
                precommit=False,
                message=message,
            )
            return VerificationPhaseOutcome(
                result="failed",
                verification_status=f"failed:{command}",
                verification_failed_command=command,
                verification_output=verification_output,
                command_timings=command_timings,
                feedback=feedback,
            )

    return VerificationPhaseOutcome(
        result="passed",
        verification_status="passed",
        verification_failed_command=None,
        verification_output="\n".join(command_outputs),
        command_timings=command_timings,
        feedback=None,
    )


def _reviewer_not_run_outcome() -> ReviewerPhaseOutcome:
    return ReviewerPhaseOutcome(
        result="passed",
        failed_gate=None,
        reviewer_status="not_run",
        reviewer_output="",
        command_timings=[],
        feedback=None,
    )


def _reviewer_not_configured_outcome() -> ReviewerPhaseOutcome:
    return ReviewerPhaseOutcome(
        result="passed",
        failed_gate=None,
        reviewer_status="not_configured",
        reviewer_output="",
        command_timings=[],
        feedback=None,
    )


def _reviewer_success_outcome(result: ChecksRunResult) -> ReviewerPhaseOutcome:
    status = "passed" if result.output else "not_run"
    decision = "approve" if status == "passed" else None
    return ReviewerPhaseOutcome(
        result="passed",
        failed_gate=None,
        reviewer_status=status,
        reviewer_decision=decision,
        failed_reviewer_id=None,
        reviewer_output=result.output,
        command_timings=[],
        feedback=None,
    )


def _reviewer_failure_outcome(
    iteration_inputs: FeatureIterationInputs,
    dependencies: ReviewerPhaseDependencies,
    *,
    archived_path: Path | None,
    result: ChecksRunResult,
) -> ReviewerPhaseOutcome:
    if archived_path is not None:
        dependencies.restore_archived_feature(
            archived_path,
            iteration_inputs.feature_path,
        )

    failed_gate = _checks_failure_gate_id(result, default="reviewer")
    return ReviewerPhaseOutcome(
        result="failed",
        failed_gate=failed_gate,
        reviewer_status=f"failed:{failed_gate}",
        reviewer_decision="request_changes",
        failed_reviewer_id=result.failed_check_id,
        reviewer_output=result.output,
        command_timings=[],
        feedback=_checks_failure_feedback(result),
    )


def run_reviewer_phase(
    iteration_inputs: FeatureIterationInputs,
    feature: dict[str, Any] | None,
    archived_in_iteration: bool,
    archived_path: Path | None,
    dependencies: ReviewerPhaseDependencies,
) -> ReviewerPhaseOutcome:
    """Run reviewer policy after deterministic gates and before completion commit."""
    if feature is None or not archived_in_iteration:
        return _reviewer_not_run_outcome()

    checks_path = iteration_inputs.project_root / "harness" / "checks.yaml"
    if not checks_path.exists():
        return _reviewer_not_configured_outcome()

    feature_path = archived_path or iteration_inputs.feature_path
    result = _run_loop_triggered_checks(
        LoopTriggeredChecksRequest(
            project_root=iteration_inputs.project_root,
            phase=HarnessCheckPhase.FEATURE_DONE,
            feature_path=feature_path,
            run_agent_fn=dependencies.run_agent_fn,
            feedback=iteration_inputs.feedback,
            collect_changed_paths=dependencies.collect_changed_paths,
        )
    )

    if result.ok:
        return _reviewer_success_outcome(result)
    return _reviewer_failure_outcome(
        iteration_inputs,
        dependencies,
        archived_path=archived_path,
        result=result,
    )


def run_completion_commit_phase(
    iteration_inputs: FeatureIterationInputs,
    post_feature: dict[str, Any] | None,
    archived_in_iteration: bool,
    archived_path: Path | None,
    dependencies: CompletionPhaseDependencies,
) -> CompletionCommitOutcome:
    """Commit archived done-feature changes and rollback archive on failures."""
    if not archived_in_iteration:
        return CompletionCommitOutcome(
            completed=False,
            completion_commit_succeeded=False,
            result="passed",
            failed_gate=None,
            next_action="retry_same_feature",
            feedback=None,
        )

    if post_feature is None:
        return CompletionCommitOutcome(
            completed=False,
            completion_commit_succeeded=False,
            result="failed",
            failed_gate="feature_archive",
            next_action="retry_same_feature",
            feedback="archived feature payload missing before completion commit",
        )

    commit_ok, commit_failed_gate, commit_output = (
        dependencies.commit_feature_completion(
            iteration_inputs.project_root,
            post_feature,
        )
    )
    if commit_ok:
        return CompletionCommitOutcome(
            completed=True,
            completion_commit_succeeded=True,
            result="passed",
            failed_gate=None,
            next_action="select_next_feature",
            feedback=None,
        )

    rollback_output = ""
    if archived_path is not None:
        restored_ok, restore_error = dependencies.restore_archived_feature(
            archived_path,
            iteration_inputs.feature_path,
        )
        if not restored_ok:
            rollback_output = f"\narchive rollback failed: {restore_error}"

    completion_output = f"{commit_output}{rollback_output}".strip()

    completion_command: str
    if commit_failed_gate == "git_add":
        completion_command = "git add -A -- ."
    else:
        commit_subject = feature_completion_commit_subject(post_feature)
        completion_command = (
            "git -c user.name=engineeringagent -c user.email=engineeringagent@local "
            f"commit -m {shlex.quote(commit_subject)}"
        )

    feedback = build_command_failure_feedback(
        phase="completion_commit",
        gate=commit_failed_gate,
        command=completion_command,
        precommit=False,
        message=(
            "Completion commit failed. Rerun the command to see full diagnostics."
        ),
    )

    return CompletionCommitOutcome(
        completed=False,
        completion_commit_succeeded=False,
        result="failed",
        failed_gate=commit_failed_gate,
        next_action="retry_same_feature",
        feedback=feedback,
        completion_output=completion_output,
    )
