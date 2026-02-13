"""Loop runtime gate/completion phase helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .models import CompletionCommitOutcome, FeatureIterationInputs, GatePhaseOutcome


@dataclass(frozen=True)
class GatePhaseDependencies:
    load_gate_config: Callable[[Path], dict[str, Any]]
    run_profile: Callable[
        [dict[str, Any], str, Path, bool], tuple[bool, str | None, str]
    ]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]


@dataclass(frozen=True)
class CompletionPhaseDependencies:
    commit_feature_completion: Callable[
        [Path, dict[str, Any]], tuple[bool, str | None, str]
    ]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]


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
