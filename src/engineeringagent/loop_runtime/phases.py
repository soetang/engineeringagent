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
from ..prompts.retry_feedback import (
    build_command_failure_retry_feedback,
    build_fitness_failure_retry_feedback,
    build_reviewer_feedback_retry_feedback,
)
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


def _payload_get_str(payload: object, key: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _payload_get_list_of_dicts(payload: object, key: str) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get(key)
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


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


class VerificationPhaseDependencies(BaseModel):
    """Injectable dependencies for the verification phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_shell_command: Callable[[Path, str], Any]


class ReviewerPhaseDependencies(BaseModel):
    """Injectable dependencies for the reviewer phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    collect_changed_paths: Callable[..., Any]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]
    run_agent_fn: Callable[..., Any] | None = None


def run_gate_phase(  # noqa: C901
    iteration_inputs: FeatureIterationInputs,
    archived_in_iteration: bool,
    archived_path: Path | None,
    dependencies: GatePhaseDependencies,
) -> GatePhaseOutcome:
    """Run post-implement gates and perform archive rollback on failure."""
    checks_path = iteration_inputs.project_root / "harness" / "checks.yaml"
    if not checks_path.exists():
        if iteration_inputs.run_all:
            output = "missing harness/checks.yaml (required for --all)"
            return GatePhaseOutcome(
                result="failed",
                failed_gate="checks_config",
                gate_status="failed:checks_config",
                gate_output=output,
                command_timings=[],
                hook_feedback=output,
            )
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="not_configured",
            gate_output="",
            command_timings=[],
            hook_feedback=None,
        )

    outputs: list[str] = []
    command_timings: list[CommandTiming] = []
    hook_feedback: str | None = None
    failed_gate: str | None = None

    def _command_for_failed_check(result: ChecksRunResult) -> str | None:
        if not result.failed_check_id:
            return None
        for invocation in reversed(result.command_invocations):
            if invocation.check_id == result.failed_check_id:
                command = invocation.command.strip()
                return command or None
        return None

    def _run_gate_groups(phase: HarnessCheckPhase) -> ChecksRunResult:
        result = run_checks(
            iteration_inputs.project_root,
            phase=phase,
            checks=["commands", "fitness"],
            verbose_output=iteration_inputs.verbose_output,
            collect_changed_paths=dependencies.collect_changed_paths,
        )

        _append_gate_command_timings(result.command_invocations, command_timings)
        return result

    last_result: ChecksRunResult = _run_gate_groups(HarnessCheckPhase.ITERATION_END)
    if last_result.output:
        outputs.append(last_result.output)
    if last_result.ok and archived_in_iteration:
        last_result = _run_gate_groups(HarnessCheckPhase.FEATURE_DONE)
        if last_result.output:
            outputs.append(last_result.output)

    ok = last_result.ok
    if last_result.failed_group == "config":
        failed_gate = "checks_config"
    else:
        failed_gate = last_result.failed_check_id

    combined_output = "\n".join(part for part in outputs if part).strip()

    if ok:
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="passed",
            gate_output=combined_output,
            command_timings=command_timings,
            hook_feedback=None,
        )

    failure_result: ChecksRunResult = last_result

    if failure_result.failed_group == "commands":
        payload = failure_result.failed_payload
        command = _payload_get_str(payload, "command")
        command = command or _command_for_failed_check(failure_result)
        hook_feedback = build_command_failure_retry_feedback(
            phase="gates",
            gate=failure_result.failed_check_id,
            command=command or "unknown",
            precommit=False,
            message="Command check failed. Rerun the command to see full diagnostics.",
        )
    elif failure_result.failed_group == "fitness":
        payload = failure_result.failed_payload
        failed_rules = _payload_get_list_of_dicts(payload, "failed_rules")
        if failed_rules:
            hook_feedback = build_fitness_failure_retry_feedback(
                gate=failure_result.failed_check_id,
                command=(
                    "uv run engineeringagent checks run --checks fitness --phase iteration_end"
                ),
                failed_rules=failed_rules,
            )
    hook_feedback = hook_feedback or combined_output or "checks failed"

    if archived_in_iteration and archived_path is not None:
        restored_ok, restore_error = dependencies.restore_archived_feature(
            archived_path,
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
        command_timings=command_timings,
        hook_feedback=hook_feedback,
    )


def run_verification_phase(
    iteration_inputs: FeatureIterationInputs,
    verification_commands: list[str],
    dependencies: VerificationPhaseDependencies,
) -> VerificationPhaseOutcome:
    """Run selected-subtask verification commands for the current iteration."""
    if not verification_commands:
        return VerificationPhaseOutcome(
            result="passed",
            verification_status="not_run",
            verification_failed_command=None,
            verification_output="",
            command_timings=[],
            hook_feedback=None,
        )

    command_outputs: list[str] = []
    command_timings: list[CommandTiming] = []
    for command in verification_commands:
        print(f"Verification step: {command}")
        started_epoch_sec = int(time.time())
        proc = dependencies.run_shell_command(iteration_inputs.project_root, command)
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
            hook_feedback = build_command_failure_retry_feedback(
                phase="verification",
                gate=None,
                command=command,
                precommit=False,
                message=(
                    "Verification command failed. Rerun the command to see full diagnostics."
                ),
            )
            return VerificationPhaseOutcome(
                result="failed",
                verification_status=f"failed:{command}",
                verification_failed_command=command,
                verification_output=verification_output,
                command_timings=command_timings,
                hook_feedback=hook_feedback,
            )

    return VerificationPhaseOutcome(
        result="passed",
        verification_status="passed",
        verification_failed_command=None,
        verification_output="\n".join(command_outputs),
        command_timings=command_timings,
        hook_feedback=None,
    )


def run_reviewer_phase(  # noqa: C901
    iteration_inputs: FeatureIterationInputs,
    feature: dict[str, Any] | None,
    archived_in_iteration: bool,
    archived_path: Path | None,
    dependencies: ReviewerPhaseDependencies,
) -> ReviewerPhaseOutcome:
    """Run reviewer policy after deterministic gates and before completion commit."""
    command_timings: list[CommandTiming] = []
    if feature is None or not archived_in_iteration:
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="not_run",
            reviewer_output="",
            command_timings=command_timings,
            hook_feedback=None,
        )

    checks_path = iteration_inputs.project_root / "harness" / "checks.yaml"
    if not checks_path.exists():
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="not_configured",
            reviewer_output="",
            command_timings=command_timings,
            hook_feedback=None,
        )

    feature_path = archived_path or iteration_inputs.feature_path
    result = run_checks(
        iteration_inputs.project_root,
        phase=HarnessCheckPhase.FEATURE_DONE,
        checks=["reviewers"],
        feature_path=feature_path,
        run_agent_fn=dependencies.run_agent_fn,
        prior_feedback=iteration_inputs.hook_feedback,
        collect_changed_paths=dependencies.collect_changed_paths,
    )

    reviewer_output = result.output
    if result.ok:
        status = "passed" if reviewer_output else "not_run"
        decision = "approve" if status == "passed" else None
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status=status,
            reviewer_decision=decision,
            failed_reviewer_id=None,
            reviewer_output=reviewer_output,
            command_timings=command_timings,
            hook_feedback=None,
        )

    if archived_path is not None:
        dependencies.restore_archived_feature(
            archived_path, iteration_inputs.feature_path
        )

    raw_payload = result.failed_payload
    reviewer_id = result.failed_check_id or "unknown"
    reviewer_phase = "feature_done"
    decision_payload: dict[str, object] = {
        "decision": "request_changes",
        "summary": "(reviewer payload missing)",
        "required_actions": [],
    }
    if isinstance(raw_payload, dict) and raw_payload.get("kind") == "reviewer_feedback":
        value = raw_payload.get("reviewer_id")
        if isinstance(value, str) and value.strip():
            reviewer_id = value
        phase_value = raw_payload.get("reviewer_phase")
        if phase_value in {"iteration_end", "feature_done"}:
            reviewer_phase = phase_value
        decision_value = raw_payload.get("decision")
        if isinstance(decision_value, dict):
            decision_payload = decision_value

    feedback = build_reviewer_feedback_retry_feedback(
        reviewer_id=reviewer_id,
        reviewer_phase=reviewer_phase,
        decision=decision_payload,
    )
    decision_name_raw = decision_payload.get("decision")
    decision_name = (
        decision_name_raw
        if isinstance(decision_name_raw, str) and decision_name_raw.strip()
        else "request_changes"
    )

    return ReviewerPhaseOutcome(
        result="failed",
        failed_gate="reviewer_request_changes",
        reviewer_status="failed:request_changes",
        reviewer_decision=decision_name,
        failed_reviewer_id=result.failed_check_id,
        reviewer_output=reviewer_output,
        command_timings=command_timings,
        hook_feedback=feedback,
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
            hook_feedback=None,
        )

    if post_feature is None:
        return CompletionCommitOutcome(
            completed=False,
            completion_commit_succeeded=False,
            result="failed",
            failed_gate="feature_archive",
            next_action="retry_same_feature",
            hook_feedback="archived feature payload missing before completion commit",
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
            hook_feedback=None,
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

    hook_feedback = build_command_failure_retry_feedback(
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
        hook_feedback=hook_feedback,
        completion_output=completion_output,
    )
