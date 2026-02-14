"""Loop runtime gate/completion phase helpers."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from .models import (
    CompletionCommitOutcome,
    FeatureIterationInputs,
    GatePhaseOutcome,
    VerificationPhaseOutcome,
)


class GatePhaseDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    load_gate_config: Callable[[Path], dict[str, Any]]
    run_profile: Callable[
        [dict[str, Any], str, Path, bool], tuple[bool, str | None, str]
    ]
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


def run_gate_phase(
    iteration_inputs: FeatureIterationInputs,
    gates_path: Path,
    archived_in_iteration: bool,
    archived_path: Path | None,
    dependencies: GatePhaseDependencies,
) -> GatePhaseOutcome:
    """Run post-implement gates and perform archive rollback on failure."""
    gate_config = dependencies.load_gate_config(gates_path)
    ok, failed, gate_output = dependencies.run_profile(
        gate_config,
        iteration_inputs.gate_profile,
        iteration_inputs.project_root,
        True,
    )
    if iteration_inputs.verbose_output and gate_output:
        print(gate_output)

    if ok:
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="passed",
            gate_output=gate_output,
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
            hook_feedback=None,
        )

    command_outputs: list[str] = []
    for command in verification_commands:
        print(f"Verification step: {command}")
        proc = dependencies.run_shell_command(iteration_inputs.project_root, command)
        if iteration_inputs.verbose_output:
            if proc.stdout:
                print(proc.stdout, end="")
            if proc.stderr:
                print(proc.stderr, end="", file=sys.stderr)
        output = (proc.stdout or "") + (proc.stderr or "")
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
                hook_feedback=verification_output,
            )

    return VerificationPhaseOutcome(
        result="passed",
        verification_status="passed",
        verification_failed_command=None,
        verification_output="\n".join(command_outputs),
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
    return CompletionCommitOutcome(
        completed=False,
        completion_commit_succeeded=False,
        result="failed",
        failed_gate=commit_failed_gate,
        next_action="retry_same_feature",
        hook_feedback=f"{commit_output}{rollback_output}".strip(),
    )
