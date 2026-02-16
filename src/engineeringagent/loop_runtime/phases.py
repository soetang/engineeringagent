"""Loop runtime gate/completion phase helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import time
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from .models import (
    CommandTiming,
    CompletionCommitOutcome,
    FeatureIterationInputs,
    GatePhaseOutcome,
    ReviewerPhaseOutcome,
    VerificationPhaseOutcome,
)
from ..reviewers import (
    DECISION_APPROVE,
    DECISION_REQUEST_CHANGES,
    DECISION_WARNING,
    increment_blocking_reviewer_retry_count,
)
from .time_format import utc_iso_from_epoch_sec


def _format_reviewer_feedback(summary: str, required_actions: list[str]) -> str:
    """Compose deterministic reviewer feedback with actionable follow-ups."""
    message = summary.strip()
    actions = [action.strip() for action in required_actions if action.strip()]
    if not actions:
        return message
    actions_block = "\n".join(f"- {action}" for action in actions)
    return f"{message}\nrequired_actions:\n{actions_block}"


def _normalize_feedback_context(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if not value.strip():
        return None
    return value.strip("\n")


def _append_feedback_context(message: str, feedback_context: str | None) -> str:
    if not feedback_context:
        return message
    return f"{message}\nfeedback_context:\n{feedback_context}"


def _format_forwarded_reviewer_feedback(
    reviewer_id: str,
    reviewer_mode: str,
    decision_name: str,
    reviewer_feedback: str,
) -> str:
    """Compose deterministic retry feedback forwarded to the next implement pass."""
    return (
        f"reviewer '{reviewer_id}' feedback "
        f"(mode={reviewer_mode}, decision={decision_name}): "
        f"{reviewer_feedback}"
    )


def _resolve_passed_reviewer_decision(
    *,
    ran_reviewer: bool,
    first_non_approve_decision: str | None,
) -> str | None:
    """Return deterministic reviewer decision metadata for passed outcomes."""
    if first_non_approve_decision is not None:
        return first_non_approve_decision
    if ran_reviewer:
        return DECISION_APPROVE
    return None


class GatePhaseDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    load_gate_config: Callable[[Path], dict[str, Any]]
    run_profile: Callable[..., tuple[bool, str | None, str]]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]


class CompletionPhaseDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    commit_feature_completion: Callable[
        [Path, dict[str, Any]], tuple[bool, str | None, str]
    ]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]


class VerificationPhaseDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_shell_command: Callable[[Path, str], Any]


class ReviewerPhaseDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    load_reviewer_config: Callable[[Path], dict[str, Any]]
    collect_changed_paths: Callable[..., Any]
    load_reviewers_state: Callable[[Path], dict[str, Any]]
    save_reviewers_state: Callable[[Path, dict[str, Any]], None]
    plan_reviewers: Callable[..., list[dict[str, str]]]
    evaluate_cached_reviewer_approval: Callable[..., tuple[bool, str]]
    run_reviewer: Callable[..., dict[str, Any]]
    record_reviewer_approval: Callable[..., None]
    advisory_followup_required: Callable[[dict[str, Any], str], bool]
    set_advisory_followup_required: Callable[[dict[str, Any], str], None]
    clear_advisory_followup_required: Callable[[dict[str, Any], str], None]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]
    start_agent: Callable[..., Any]


def run_gate_phase(
    iteration_inputs: FeatureIterationInputs,
    gates_path: Path,
    archived_in_iteration: bool,
    archived_path: Path | None,
    dependencies: GatePhaseDependencies,
) -> GatePhaseOutcome:
    """Run post-implement gates and perform archive rollback on failure."""
    gate_config = dependencies.load_gate_config(gates_path)

    command_timings: list[CommandTiming] = []

    def _timing_hook(
        gate_name: str,
        command: str,
        started_epoch_sec: int,
        ended_epoch_sec: int,
    ) -> None:
        command_timings.append(
            CommandTiming(
                phase="gates",
                gate=gate_name,
                command=command,
                started_at=utc_iso_from_epoch_sec(started_epoch_sec),
                ended_at=utc_iso_from_epoch_sec(ended_epoch_sec),
                duration_sec=max(0, ended_epoch_sec - started_epoch_sec),
            )
        )

    ok, failed, gate_output = dependencies.run_profile(
        gate_config,
        iteration_inputs.gate_profile,
        iteration_inputs.project_root,
        True,
        timing_hook=_timing_hook,
    )
    if iteration_inputs.verbose_output and gate_output:
        print(gate_output)

    if ok:
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="passed",
            gate_output=gate_output,
            command_timings=command_timings,
            hook_feedback=None,
        )

    if archived_in_iteration and archived_path is not None:
        restored_ok, restore_error = dependencies.restore_archived_feature(
            archived_path,
            iteration_inputs.feature_path,
        )
        if not restored_ok:
            rollback_output = f"\narchive rollback failed: {restore_error}"
            gate_output = f"{gate_output}{rollback_output}".strip()

    return GatePhaseOutcome(
        result="failed",
        failed_gate=failed,
        gate_status=f"failed:{failed or 'unknown'}",
        gate_output=gate_output,
        command_timings=command_timings,
        hook_feedback=gate_output
        or (f"gate '{failed or 'unknown'}' failed with no captured output"),
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
            return VerificationPhaseOutcome(
                result="failed",
                verification_status=f"failed:{command}",
                verification_failed_command=command,
                verification_output=verification_output,
                command_timings=command_timings,
                hook_feedback=verification_output,
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
    if feature is None:
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="not_run",
            reviewer_output="",
            command_timings=command_timings,
            hook_feedback=None,
        )

    reviewers_path = iteration_inputs.project_root / "harness" / "reviewers.yaml"
    config = dependencies.load_reviewer_config(reviewers_path)
    profiles = config.get("profiles", {})
    if not isinstance(profiles, dict) or iteration_inputs.gate_profile not in profiles:
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="not_configured",
            reviewer_output="",
            command_timings=command_timings,
            hook_feedback=None,
        )

    phase = "feature_done" if archived_in_iteration else "iteration_end"
    changed_paths = dependencies.collect_changed_paths(iteration_inputs.project_root)
    planned = dependencies.plan_reviewers(
        config,
        iteration_inputs.gate_profile,
        phase=phase,
        changed_paths=changed_paths,
    )

    if not planned:
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="not_run",
            reviewer_output="",
            command_timings=command_timings,
            hook_feedback=None,
        )

    feature_id = str(feature.get("id", ""))
    state = dependencies.load_reviewers_state(iteration_inputs.project_root)
    pending_advisory_followup = dependencies.advisory_followup_required(
        state, feature_id
    )
    followup_satisfied_in_iteration = False
    if pending_advisory_followup:
        dependencies.clear_advisory_followup_required(state, feature_id)
        pending_advisory_followup = False
        followup_satisfied_in_iteration = True

    reviewers = config.get("reviewers", {})
    summaries: list[str] = []
    forwarded_feedback: list[str] = []
    advisory_feedback: list[str] = []
    blocking_feedback: list[str] = []
    blocking_exhausted_warnings: list[str] = []
    blocking_exhausted_failures: list[str] = []
    ran_reviewer = False
    first_non_approve_reviewer_id: str | None = None
    first_non_approve_decision: str | None = None

    for entry in planned:
        reviewer_id = entry["reviewer"]
        if entry["decision"] != "run":
            summaries.append(f"[reviewer:{reviewer_id}] skip reason={entry['reason']}")
            continue

        reviewer = reviewers.get(reviewer_id, {})
        if not isinstance(reviewer, dict):
            continue
        reuse, reuse_reason = dependencies.evaluate_cached_reviewer_approval(
            state,
            feature_id=feature_id,
            reviewer_id=reviewer_id,
            reviewer=reviewer,
            changed_paths=changed_paths,
        )
        if reuse:
            summaries.append(
                f"[reviewer:{reviewer_id}] decision=approve reused={reuse_reason}"
            )
            continue

        started_epoch_sec = int(time.time())
        decision = dependencies.run_reviewer(
            iteration_inputs.project_root,
            reviewer_id,
            reviewer,
            feature_id=feature_id,
            feature_path=archived_path or iteration_inputs.feature_path,
            changed_paths=changed_paths,
            prior_feedback=iteration_inputs.hook_feedback,
            start_agent_fn=dependencies.start_agent,
        )
        ended_epoch_sec = max(started_epoch_sec, int(time.time()))
        command_timings.append(
            CommandTiming(
                phase="reviewers",
                reviewer_id=reviewer_id,
                command="run_reviewer",
                started_at=utc_iso_from_epoch_sec(started_epoch_sec),
                ended_at=utc_iso_from_epoch_sec(ended_epoch_sec),
                duration_sec=ended_epoch_sec - started_epoch_sec,
            )
        )
        dependencies.record_reviewer_approval(
            state,
            feature_id=feature_id,
            reviewer_id=reviewer_id,
            decision=str(decision.get("decision", "")),
        )

        reviewer_mode = str(reviewer.get("approval", {}).get("mode", "advisory"))
        decision_name = str(decision.get("decision", "request_changes"))
        ran_reviewer = True
        if decision_name != DECISION_APPROVE and first_non_approve_decision is None:
            first_non_approve_reviewer_id = reviewer_id
            first_non_approve_decision = decision_name
        summary = str(decision.get("summary", ""))
        required_actions_raw = decision.get("required_actions", [])
        required_actions = (
            required_actions_raw if isinstance(required_actions_raw, list) else []
        )
        feedback_context = _normalize_feedback_context(reviewer.get("feedback_context"))
        forwarded_context = (
            feedback_context
            if decision_name in (DECISION_REQUEST_CHANGES, DECISION_WARNING)
            else None
        )
        reviewer_feedback_message = _format_reviewer_feedback(summary, required_actions)
        reviewer_feedback = _append_feedback_context(
            reviewer_feedback_message,
            forwarded_context,
        )
        forwarded_feedback.append(
            _format_forwarded_reviewer_feedback(
                reviewer_id,
                reviewer_mode,
                decision_name,
                reviewer_feedback,
            )
        )
        summaries.append(
            f"[reviewer:{reviewer_id}] mode={reviewer_mode} decision={decision_name} summary={summary}"
        )

        if reviewer_mode == "blocking" and decision_name == DECISION_REQUEST_CHANGES:
            approval = reviewer.get("approval", {})
            max_retries = int(approval.get("max_retries", 2))
            continue_on_exhausted = bool(approval.get("continue_on_exhausted", True))
            retry_count = increment_blocking_reviewer_retry_count(
                state,
                feature_id=feature_id,
                reviewer_id=reviewer_id,
            )
            if retry_count <= max_retries:
                blocking_feedback.append(
                    (
                        f"reviewer '{reviewer_id}' requested changes "
                        f"(attempt {retry_count}/{max_retries + 1}): "
                        f"{reviewer_feedback}"
                    )
                )
                continue

            exhausted_message = (
                f"reviewer '{reviewer_id}' exhausted retries "
                f"(max_retries={max_retries}): {reviewer_feedback}"
            )
            if continue_on_exhausted:
                blocking_exhausted_warnings.append(exhausted_message)
            else:
                blocking_exhausted_failures.append(exhausted_message)
            continue

        if reviewer_mode == "advisory":
            advisory_feedback.append(
                f"reviewer '{reviewer_id}' advisory feedback: {reviewer_feedback}"
            )

    reviewer_output = "\n".join(summaries)
    if blocking_exhausted_failures:
        if archived_in_iteration and archived_path is not None:
            dependencies.restore_archived_feature(
                archived_path, iteration_inputs.feature_path
            )
        dependencies.save_reviewers_state(iteration_inputs.project_root, state)
        feedback = "\n".join(blocking_exhausted_failures)
        return ReviewerPhaseOutcome(
            result="failed",
            failed_gate="reviewer_blocking_exhausted",
            reviewer_status="failed:blocking_exhausted",
            reviewer_decision=first_non_approve_decision,
            failed_reviewer_id=first_non_approve_reviewer_id,
            reviewer_output=reviewer_output,
            command_timings=command_timings,
            hook_feedback=feedback,
        )

    if blocking_feedback:
        if archived_in_iteration and archived_path is not None:
            dependencies.restore_archived_feature(
                archived_path, iteration_inputs.feature_path
            )
        dependencies.save_reviewers_state(iteration_inputs.project_root, state)
        feedback = "\n".join(blocking_feedback)
        return ReviewerPhaseOutcome(
            result="failed",
            failed_gate="reviewer_blocking",
            reviewer_status="failed:blocking",
            reviewer_decision=first_non_approve_decision,
            failed_reviewer_id=first_non_approve_reviewer_id,
            reviewer_output=reviewer_output,
            command_timings=command_timings,
            hook_feedback=feedback,
        )

    if (
        advisory_feedback
        and phase == "feature_done"
        and not pending_advisory_followup
        and not followup_satisfied_in_iteration
    ):
        dependencies.set_advisory_followup_required(state, feature_id)
        if archived_in_iteration and archived_path is not None:
            dependencies.restore_archived_feature(
                archived_path, iteration_inputs.feature_path
            )
        dependencies.save_reviewers_state(iteration_inputs.project_root, state)
        feedback = "\n".join(advisory_feedback)
        return ReviewerPhaseOutcome(
            result="failed",
            failed_gate="reviewer_advisory_followup",
            reviewer_status="failed:advisory_followup",
            reviewer_decision=first_non_approve_decision,
            failed_reviewer_id=first_non_approve_reviewer_id,
            reviewer_output=reviewer_output,
            command_timings=command_timings,
            hook_feedback=feedback,
        )

    dependencies.save_reviewers_state(iteration_inputs.project_root, state)
    if blocking_exhausted_warnings:
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="passed:blocking_exhausted_continue",
            reviewer_decision=first_non_approve_decision,
            failed_reviewer_id=None,
            reviewer_output=reviewer_output,
            command_timings=command_timings,
            hook_feedback="\n".join(blocking_exhausted_warnings),
        )

    if advisory_feedback:
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="passed:advisory",
            reviewer_decision=first_non_approve_decision,
            failed_reviewer_id=None,
            reviewer_output=reviewer_output,
            command_timings=command_timings,
            hook_feedback="\n".join(advisory_feedback),
        )

    return ReviewerPhaseOutcome(
        result="passed",
        failed_gate=None,
        reviewer_status="passed",
        reviewer_decision=_resolve_passed_reviewer_decision(
            ran_reviewer=ran_reviewer,
            first_non_approve_decision=first_non_approve_decision,
        ),
        failed_reviewer_id=None,
        reviewer_output=reviewer_output,
        command_timings=command_timings,
        hook_feedback="\n".join(forwarded_feedback) if forwarded_feedback else None,
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
    return CompletionCommitOutcome(
        completed=False,
        completion_commit_succeeded=False,
        result="failed",
        failed_gate=commit_failed_gate,
        next_action="retry_same_feature",
        hook_feedback=f"{commit_output}{rollback_output}".strip(),
    )
