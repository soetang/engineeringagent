"""Loop runtime gate/completion phase helpers."""

from __future__ import annotations

from pathlib import Path
import shlex
import sys
import time
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from ..changed_paths import ChangedPathsResult
from ..specs import HarnessCheckPhase
from ..harness_checks_runtime import (
    PlannedCommandChecksInputs,
    iter_planned_reviewer_checks,
    load_checks_document,
    plan_reviewer_checks,
    run_planned_command_checks,
    run_planned_fitness_checks_with_failures,
)

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
)
from .time_format import utc_iso_from_epoch_sec
from ..retry_feedback.builders import (
    build_command_failure_retry_feedback,
    build_fitness_failure_retry_feedback,
    build_reviewer_feedback_retry_feedback,
)
from ..feature_commit import feature_completion_commit_subject


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


class GatePhaseDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]
    collect_changed_paths: Callable[[Path], ChangedPathsResult]
    run_shell_command: Callable[[Path, str], Any]


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
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]
    start_agent: Callable[..., Any]


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

    try:
        checks_doc = load_checks_document(checks_path)
    except Exception as exc:  # noqa: BLE001
        output = f"failed to load harness/checks.yaml: {exc}".strip()
        return GatePhaseOutcome(
            result="failed",
            failed_gate="checks_config",
            gate_status="failed:checks_config",
            gate_output=output,
            command_timings=[],
            hook_feedback=output,
        )

    changed_paths = dependencies.collect_changed_paths(iteration_inputs.project_root)
    command_timings: list[CommandTiming] = []
    command_failure_feedback: str | None = None
    fitness_failure_feedback: str | None = None

    ok, failed, output, timings = run_planned_command_checks(
        PlannedCommandChecksInputs(
            iteration_inputs.project_root,
            checks_doc,
            HarnessCheckPhase.ITERATION_END,
            changed_paths,
            iteration_inputs.verbose_output,
            dependencies.run_shell_command,
        )
    )
    command_timings.extend(timings)

    if not ok and failed:
        failed_command = next(
            (
                timing.command
                for timing in reversed(timings)
                if timing.gate == failed and timing.command
            ),
            None,
        )
        command_failure_feedback = build_command_failure_retry_feedback(
            phase="gates",
            gate=failed,
            command=failed_command or "unknown",
            precommit=False,
            message="Command check failed. Rerun the command to see full diagnostics.",
        )

    if ok:
        ok, failed, fitness_output, fitness_timings, failed_rules = (
            run_planned_fitness_checks_with_failures(
                project_root=iteration_inputs.project_root,
                doc=checks_doc,
                phase=HarnessCheckPhase.ITERATION_END,
                changed_paths=changed_paths,
            )
        )
        command_timings.extend(fitness_timings)
        output = "\n".join(part for part in (output, fitness_output) if part).strip()

        if not ok and failed and failed_rules:
            fitness_failure_feedback = build_fitness_failure_retry_feedback(
                gate=failed,
                command="uv run python -m engineeringagent.cli fitness run --format json",
                failed_rules=failed_rules,
            )

    if ok and archived_in_iteration:
        ok, failed, feature_output, feature_timings = run_planned_command_checks(
            PlannedCommandChecksInputs(
                iteration_inputs.project_root,
                checks_doc,
                HarnessCheckPhase.FEATURE_DONE,
                changed_paths,
                iteration_inputs.verbose_output,
                dependencies.run_shell_command,
            )
        )
        command_timings.extend(feature_timings)

        if not ok and failed:
            failed_command = next(
                (
                    timing.command
                    for timing in reversed(feature_timings)
                    if timing.gate == failed and timing.command
                ),
                None,
            )
            command_failure_feedback = build_command_failure_retry_feedback(
                phase="gates",
                gate=failed,
                command=failed_command or "unknown",
                precommit=False,
                message=(
                    "Command check failed. Rerun the command to see full diagnostics."
                ),
            )

        if ok:
            ok, failed, fitness_output, fitness_timings, failed_rules = (
                run_planned_fitness_checks_with_failures(
                    project_root=iteration_inputs.project_root,
                    doc=checks_doc,
                    phase=HarnessCheckPhase.FEATURE_DONE,
                    changed_paths=changed_paths,
                )
            )
            command_timings.extend(fitness_timings)
            feature_output = "\n".join(
                part for part in (feature_output, fitness_output) if part
            ).strip()

            if not ok and failed and failed_rules:
                fitness_failure_feedback = build_fitness_failure_retry_feedback(
                    gate=failed,
                    command=(
                        "uv run python -m engineeringagent.cli fitness run --format json"
                    ),
                    failed_rules=failed_rules,
                )
        output = "\n".join(part for part in (output, feature_output) if part).strip()

    if ok:
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="passed",
            gate_output=output,
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
            output = f"{output}{rollback_output}".strip()

    return GatePhaseOutcome(
        result="failed",
        failed_gate=failed,
        gate_status=f"failed:{failed or 'unknown'}",
        gate_output=output,
        command_timings=command_timings,
        hook_feedback=command_failure_feedback
        or fitness_failure_feedback
        or output
        or (f"check '{failed or 'unknown'}' failed with no captured output"),
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

    if iteration_inputs.run_all:
        checks_path = iteration_inputs.project_root / "harness" / "checks.yaml"
        try:
            checks_doc = load_checks_document(checks_path)
        except Exception as exc:  # noqa: BLE001
            output = f"failed to load harness/checks.yaml: {exc}".strip()
            return ReviewerPhaseOutcome(
                result="failed",
                failed_gate="checks_config",
                reviewer_status="failed:checks_config",
                reviewer_output=output,
                command_timings=command_timings,
                hook_feedback=output,
            )

        phase = HarnessCheckPhase.FEATURE_DONE
        changed_paths = dependencies.collect_changed_paths(
            iteration_inputs.project_root
        )
        planned = plan_reviewer_checks(
            checks_doc,
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

        summaries: list[str] = []
        ran_reviewer = False
        first_non_approve_reviewer_id: str | None = None
        first_non_approve_decision: str | None = None
        first_non_approve_payload: dict[str, Any] | None = None

        planned_by_id = {entry.check_id: entry for entry in planned}
        for reviewer_id, reviewer_def in iter_planned_reviewer_checks(
            checks_doc, planned
        ):
            entry = planned_by_id.get(reviewer_id)
            if entry is None:
                continue
            if entry.decision != "run":
                summaries.append(f"[reviewer:{reviewer_id}] skip reason={entry.reason}")
                continue

            reviewer = reviewer_def.model_dump(mode="python")
            on_change = None
            if reviewer_def.when is not None:
                on_change = reviewer_def.when.on_change
            reviewer["trigger"] = {"on_change": on_change} if on_change else {}

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

            raw_decision = str(decision.get("decision", DECISION_REQUEST_CHANGES))
            decision_name = (
                DECISION_APPROVE
                if raw_decision == DECISION_APPROVE
                else DECISION_REQUEST_CHANGES
            )
            ran_reviewer = True
            if decision_name != DECISION_APPROVE and first_non_approve_decision is None:
                first_non_approve_reviewer_id = reviewer_id
                first_non_approve_decision = decision_name
                if isinstance(decision, dict):
                    first_non_approve_payload = dict(decision)
            summary = str(decision.get("summary", ""))
            required_actions_raw = decision.get("required_actions", [])
            required_actions = (
                required_actions_raw if isinstance(required_actions_raw, list) else []
            )
            feedback_context = _normalize_feedback_context(
                reviewer.get("feedback_context")
            )
            forwarded_context = (
                feedback_context if decision_name != DECISION_APPROVE else None
            )
            reviewer_feedback_message = _format_reviewer_feedback(
                summary, required_actions
            )
            _append_feedback_context(
                reviewer_feedback_message,
                forwarded_context,
            )
            summaries.append(
                f"[reviewer:{reviewer_id}] decision={decision_name} summary={summary}"
            )

        reviewer_output = "\n".join(summaries)

        if first_non_approve_reviewer_id is not None:
            if archived_path is not None:
                dependencies.restore_archived_feature(
                    archived_path, iteration_inputs.feature_path
                )
            dependencies.save_reviewers_state(iteration_inputs.project_root, state)

            payload = first_non_approve_payload or {
                "decision": DECISION_REQUEST_CHANGES,
                "summary": "(reviewer payload missing)",
                "required_actions": [],
            }
            feedback = build_reviewer_feedback_retry_feedback(
                reviewer_id=first_non_approve_reviewer_id,
                reviewer_phase="feature_done",
                decision=payload,
            )
            return ReviewerPhaseOutcome(
                result="failed",
                failed_gate="reviewer_request_changes",
                reviewer_status="failed:request_changes",
                reviewer_decision=first_non_approve_decision,
                failed_reviewer_id=first_non_approve_reviewer_id,
                reviewer_output=reviewer_output,
                command_timings=command_timings,
                hook_feedback=feedback,
            )

        dependencies.save_reviewers_state(iteration_inputs.project_root, state)
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="passed",
            reviewer_decision=DECISION_APPROVE if ran_reviewer else None,
            failed_reviewer_id=None,
            reviewer_output=reviewer_output,
            command_timings=command_timings,
            hook_feedback=None,
        )

    return ReviewerPhaseOutcome(
        result="passed",
        failed_gate=None,
        reviewer_status="not_configured",
        reviewer_output="",
        command_timings=command_timings,
        hook_feedback=None,
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
