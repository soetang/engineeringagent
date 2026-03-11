"""Adapter-owned helpers for constructing transitional loop runtime context."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, NamedTuple, Sequence

from engineeringagent.agents import preflight, run_agent
from engineeringagent.application.feature_iteration.selection import (
    deterministic_feature_choice,
)
from engineeringagent.application.feature_iteration.models import (
    FeatureIterationInputs,
    IterationOutcome,
    IterationSummaryInputs,
)
from engineeringagent.loop_runtime.feature_state import (
    discover_active_feature_paths,
    done_features_pending_archive,
    pending_features,
    resolve_feature_paths,
)
from engineeringagent.ports import VersionControlFailure
from engineeringagent.presentation.presenters.terminal import RunOutputPresenter
from engineeringagent.specs import progress_kind_label

from .feature_selector import choose_feature_with_selector
from .run_loop_context import LoopRun, RunConfig, RunServices


def _print_run_all_snapshot_banner(resolved_paths: Sequence[Path]) -> None:
    print(
        "[run --all] Startup snapshot captured "
        f"{len(resolved_paths)} runnable feature entrypoint(s) from docs/spec/features/."
    )


def print_summary(summary: IterationSummaryInputs) -> None:
    """Print a one-line loop summary and optional gate failure."""
    presenter = RunOutputPresenter.for_current_terminal()
    if summary.attempt is not None:
        print(f"🔁 Iteration {summary.attempt} · {summary.feature_id or '-'}")
        if summary.archived_selection_path:
            print("  ♻️ Selected archived counterpart:")
            print(f"     {summary.archived_selection_path}")
        else:
            print(f"  🎯 Selected: {summary.selected_path or '-'}")
        print(f"  🛠 Implement: {summary.implement_step or '-'}")
        if summary.progress_kind:
            progress_parts = [
                part for part in (summary.progress_id, summary.progress_title) if part
            ]
            progress_reference = " - ".join(progress_parts) or "-"
            print(
                "  📍 Progress: "
                f"{progress_kind_label(summary.progress_kind)} {progress_reference}"
            )
        verification_label = summary.verification_status or "not_run"
        if (
            verification_label.startswith("failed:")
            and summary.verification_failed_command
        ):
            verification_label = f"failed ({summary.verification_failed_command})"
        print(f"  🧪 Verify: {verification_label}")
        reviewer_label = summary.reviewer_status or "not_run"
        if summary.reviewer_decision:
            reviewer_label = f"{reviewer_label} ({summary.reviewer_decision})"
        if summary.failed_reviewer_id:
            reviewer_label = f"{reviewer_label} [{summary.failed_reviewer_id}]"
        print(f"  👀 Reviewer: {reviewer_label}")
        if summary.result == "passed":
            print(f"  {presenter.format_iteration_passed_line()}")
        else:
            print(f"  {presenter.format_iteration_failed_line(summary.failed_gate)}")
            if summary.log_path:
                print(f"  📄 Log: {summary.log_path}")
        print(f"  ➡️ Next: {summary.next_action}")

    print(
        "Loop summary: "
        f"result={summary.result} feature={summary.feature_id or '-'} "
        f"attempt={summary.attempt if summary.attempt is not None else '-'} "
        f"next={summary.next_action}"
        f"{presenter.format_summary_suffix(summary.result)}"
    )
    if summary.failed_gate:
        print(presenter.format_failed_gate_line(summary.failed_gate))


def _print_run_all_no_work_message() -> None:
    print(
        "No runnable active features found for --all startup snapshot "
        "(statuses: backlog, in_progress)."
    )
    print_summary(
        IterationSummaryInputs(
            feature_id=None,
            result="no_work",
            failed_gate=None,
            attempt=None,
            next_action="stop",
        )
    )


def _build_selector_prompt(
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> str:
    choices = []
    for feature_path, feature in pending:
        choices.append(
            f"- id={feature.get('id')} status={feature.get('status')} "
            f"priority={feature.get('priority')} path={feature_path}"
        )
    return (
        "Choose the next feature spec to execute from this pending set. "
        "Reply with exactly one feature path from the list and no extra text.\n"
        f"{chr(10).join(choices)}\n"
    )


def _choose_feature_with_selector(
    project_root: Path,
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    return choose_feature_with_selector(
        project_root,
        pending,
        build_selector_prompt_fn=_build_selector_prompt,
        run_agent_fn=run_agent,
    )


def _iteration_cap_reached(total_iterations: int, max_iterations: int) -> bool:
    if total_iterations >= max_iterations:
        print(f"Reached max iteration cap ({max_iterations}) before completion.")
        return True
    return False


def _iteration_cap_reached_after_failure(
    outcome: IterationOutcome,
    *,
    total_iterations: int,
    max_iterations: int,
) -> bool:
    if total_iterations < max_iterations:
        return False
    if outcome.log_path:
        print(f"Detailed log: {outcome.log_path}")
    print(f"Reached max iteration cap ({max_iterations}) before completion.")
    return True


def _drop_completed_feature_from_snapshot(
    resolved_feature_paths: list[Path],
    completed_feature_path: Path,
) -> list[Path]:
    if completed_feature_path.exists():
        return resolved_feature_paths
    return [
        feature_path
        for feature_path in resolved_feature_paths
        if feature_path != completed_feature_path
    ]


def _runnable_feature_candidates(
    resolved_paths: list[Path],
) -> list[tuple[Path, dict[str, Any]]]:
    pending = pending_features(resolved_paths)
    if pending:
        return pending

    done_pending_archive = done_features_pending_archive(resolved_paths)
    if done_pending_archive:
        return done_pending_archive

    return []


def _terminal_iteration_failure_exit_code(outcome: IterationOutcome) -> int | None:
    if outcome.failed_gate == "git_add":
        print("Stopping loop: git_add failure requires operator intervention.")
        if outcome.log_path:
            print(f"Detailed log: {outcome.log_path}")
        return 1

    if outcome.failed_gate == "feature_missing":
        print("Stopping loop: selected feature path is missing and not recoverable.")
        if outcome.log_path:
            print(f"Detailed log: {outcome.log_path}")
        if outcome.feedback:
            print(f"Detail: {outcome.feedback}")
        return 1

    return None


def _resolve_run_targets(
    project_root: Path,
    feature_paths: Sequence[str | Path],
    run_all: bool,
) -> list[Path]:
    if run_all:
        return discover_active_feature_paths(project_root)
    return resolve_feature_paths(project_root, feature_paths)


def _emit_run_all_snapshot_feedback(
    resolved_paths: Sequence[Path], run_all: bool
) -> int | None:
    if not run_all:
        return None
    _print_run_all_snapshot_banner(resolved_paths)
    if resolved_paths:
        return None
    _print_run_all_no_work_message()
    return 0


def _handle_dry_run(
    resolved_paths: Sequence[Path],
    run_all: bool,
    dry_run: bool,
) -> int | None:
    if not dry_run:
        return None

    pending = pending_features(resolved_paths)
    if not pending:
        if run_all:
            _print_run_all_no_work_message()
        else:
            print("No pending features found in provided paths.")
            print_summary(
                IterationSummaryInputs(
                    feature_id=None,
                    result="dry_run",
                    failed_gate=None,
                    attempt=None,
                    next_action="stop",
                )
            )
        return 0

    if run_all:
        print("[dry-run] Selection is taken from the startup snapshot (no rescan).")
    feature_path, feature = deterministic_feature_choice(pending)
    feature_id = str(feature.get("id", ""))
    print(f"[dry-run] Resolved {len(resolved_paths)} feature file(s).")
    print(f"[dry-run] Selected feature={feature_id} path={feature_path}")
    print_summary(
        IterationSummaryInputs(
            feature_id=feature_id,
            result="dry_run",
            failed_gate=None,
            attempt=None,
            next_action="stop",
        )
    )
    return 0


def enforce_worktree_precondition(
    project_root: Path,
    allow_dirty: bool,
    *,
    read_worktree_status: Callable[[Path], Any],
) -> int | None:
    """Check whether the loop may run against the current worktree state."""
    try:
        status = read_worktree_status(project_root)
    except VersionControlFailure:
        reason = "unable to read git status; run inside a git repository"
        print(f"Precondition failed: {reason}")
        print("Hint: run from inside a git repository (try `git init`).")
        return 1

    if not status.dirty:
        return None
    if not allow_dirty:
        reason = "working tree must be clean before running automated loop"
        print(f"Precondition failed: {reason}")
        print(
            "Hint: re-run with --allow-dirty to explicitly continue with "
            "uncommitted code changes."
        )
        return 1

    print(
        "Allow-dirty override enabled: continuing with uncommitted code "
        "changes by explicit user opt-in."
    )
    return None


def run_selected_feature_iterations(
    loop_run: LoopRun,
    *,
    run_feature_iteration: Callable[[FeatureIterationInputs], IterationOutcome],
) -> int:
    """Execute loop iterations for the current resolved feature snapshot."""
    config = loop_run.config
    state = loop_run.state

    while True:
        resolved_paths = list(state.resolved_feature_paths)
        pending = _runnable_feature_candidates(resolved_paths)
        if not pending:
            print("All provided features are done and committed.")
            return 0

        if _iteration_cap_reached(state.total_iterations, config.max_iterations):
            return 1

        selected_feature_path, selected_feature = _choose_feature_with_selector(
            config.project_root,
            pending,
        )
        selected_feature_id = str(selected_feature.get("id", ""))
        print(f"Selected feature={selected_feature_id} path={selected_feature_path}")

        while True:
            if _iteration_cap_reached(state.total_iterations, config.max_iterations):
                return 1

            state = state.increment_total_iterations()
            outcome = run_feature_iteration(
                FeatureIterationInputs(
                    project_root=config.project_root,
                    feature_path=selected_feature_path,
                    run_all=config.run_all,
                    attempt=state.total_iterations,
                    feedback=state.feedback_for(selected_feature_path),
                    verbose_output=config.verbose_output,
                )
            )

            state = state.with_feedback(selected_feature_path, outcome.feedback)

            if outcome.completed:
                state = state.with_resolved_feature_paths(
                    _drop_completed_feature_from_snapshot(
                        resolved_paths,
                        selected_feature_path,
                    )
                )
                break

            terminal_failure_exit_code = _terminal_iteration_failure_exit_code(outcome)
            if terminal_failure_exit_code is not None:
                return terminal_failure_exit_code
            if _iteration_cap_reached_after_failure(
                outcome,
                total_iterations=state.total_iterations,
                max_iterations=config.max_iterations,
            ):
                return 1


class RunConfigOptions(NamedTuple):
    """Scalar CLI options used to build a typed `RunConfig`."""

    dry_run: bool
    run_all: bool = False
    max_iterations: int = 50
    allow_dirty: bool = False
    verbose_output: bool = False


def build_run_config(
    *,
    project_root: Path,
    feature_paths: Sequence[str | Path],
    options: RunConfigOptions,
) -> RunConfig:
    """Build run configuration from CLI-compatible scalar arguments."""
    return RunConfig(
        project_root=project_root,
        feature_paths=tuple(feature_paths),
        run_all=options.run_all,
        dry_run=options.dry_run,
        max_iterations=options.max_iterations,
        allow_dirty=options.allow_dirty,
        verbose_output=options.verbose_output,
    )


def build_loop_run(
    config: RunConfig,
    *,
    enforce_worktree_precondition_fn: Callable[[Path, bool], int | None],
    run_selected_feature_iterations_fn: Callable[[LoopRun], int],
) -> LoopRun:
    """Build the default loop runtime context from run configuration."""
    services = RunServices(
        resolve_run_targets=_resolve_run_targets,
        emit_run_all_snapshot_feedback=_emit_run_all_snapshot_feedback,
        handle_dry_run=_handle_dry_run,
        enforce_worktree_precondition=enforce_worktree_precondition_fn,
        run_permission_precheck=preflight,
        run_selected_feature_iterations=run_selected_feature_iterations_fn,
    )
    return LoopRun(config=config, services=services)
