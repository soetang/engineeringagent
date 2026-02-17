from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple, Sequence

from .changed_paths import collect_changed_paths
from .git.client import (
    add_all,
    commit as git_commit,
    head_short as git_head,
    status_porcelain,
)
from .opencode.client import run_shell_command, start_agent
from .opencode_permissions import (
    PERMISSION_REMEDIATION_HINT,
    run_permission_probe,
)
from .loop_runtime.implement import (
    run_implement_step_from_inputs,
    run_opencode_permission_precheck,
)
from .loop_runtime.models import (
    FeatureIterationInputs,
    ImplementStepInputs,
    IterationOutcome,
)
from .loop_runtime.iteration import (
    IterationPipelineDependencies,
    run_feature_iteration_pipeline,
)
from .loop_runtime.phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    VerificationPhaseDependencies,
    run_completion_commit_phase,
    run_gate_phase,
    run_reviewer_phase,
    run_verification_phase,
)
from .loop_runtime.selection import (
    choose_feature_with_selector,
    deterministic_feature_choice,
)
from .loop_runtime.feature_state import (
    _archive_completed_feature,
    _done_features_pending_archive,
    _discover_active_feature_paths,
    _evaluate_initial_feature_load,
    _pending_features,
    _ready_for_active_iteration,
    _refresh_feature_after_implement,
    _resolve_feature_paths,
    _restore_archived_feature,
    _should_archive_selected_feature,
    _touch_active_feature_for_iteration,
)
from .loop_runtime.controller import (
    run_loop_controller,
)
from .loop_runtime.run_context import LoopRun, RunConfig, RunServices
from .loop_runtime.telemetry import write_iteration_telemetry
from .loop_runtime.presentation import RunOutputPresenter
from .feature_commit import feature_completion_commit_subject


def _print_run_all_snapshot_banner(resolved_paths: Sequence[Path]) -> None:
    print(
        "[run --all] Startup snapshot captured "
        f"{len(resolved_paths)} runnable feature file(s) from docs/spec/features/*.yaml."
    )


def _print_run_all_no_work_message() -> None:
    print(
        "No runnable active features found for --all startup snapshot "
        "(statuses: backlog, in_progress)."
    )
    print_summary(None, "no_work", None, None, "stop")


def _run_opencode_permission_precheck(
    project_root: Path,
) -> bool:
    return run_opencode_permission_precheck(
        project_root=project_root,
        run_permission_probe_fn=run_permission_probe,
        permission_remediation_hint=PERMISSION_REMEDIATION_HINT,
    )


def _choose_feature_with_selector(
    project_root: Path,
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    return choose_feature_with_selector(
        project_root,
        pending,
        start_agent_fn=start_agent,
    )


def git_head_short(project_root: Path) -> str | None:
    """Return short git HEAD hash for a repository.

    Args:
        project_root: Repository root used as command cwd.

    Returns:
        Short commit hash when available, otherwise None.
    """
    proc = git_head(project_root)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def run_implement_step(
    project_root: Path,
    feature: dict[str, Any],
    feature_path: Path,
    hook_feedback: str | None,
    verbose_output: bool,
) -> tuple[bool, str | None, str]:
    """Run the implement phase for one loop iteration."""
    implement_inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature,
        feature_path=feature_path,
        hook_feedback=hook_feedback,
        verbose_output=verbose_output,
    )
    return run_implement_step_from_inputs(
        implement_inputs,
        start_agent_fn=start_agent,
    )


def _commit_feature_completion(
    project_root: Path, feature: dict[str, Any]
) -> tuple[bool, str | None, str]:
    message = feature_completion_commit_subject(feature)

    add_proc = add_all(project_root)
    if add_proc.returncode != 0:
        output = (add_proc.stdout or "") + (add_proc.stderr or "")
        return (False, "git_add", output)

    commit_proc = git_commit(project_root, message)
    output = (commit_proc.stdout or "") + (commit_proc.stderr or "")
    if commit_proc.returncode == 0:
        return (True, None, output)
    return (False, "git_commit", output)


def print_summary(
    feature_id: str | None,
    result: str,
    failed_gate: str | None,
    attempt: int | None,
    next_action: str,
    selected_path: str | None = None,
    implement_step: str | None = None,
    log_path: str | None = None,
    archived_selection_path: str | None = None,
    verification_status: str | None = None,
    verification_failed_command: str | None = None,
    reviewer_status: str | None = None,
    reviewer_decision: str | None = None,
    failed_reviewer_id: str | None = None,
) -> None:
    """Print a one-line loop summary and optional gate failure."""

    presenter = RunOutputPresenter.for_current_terminal()
    if attempt is not None:
        print(f"🔁 Iteration {attempt} · {feature_id or '-'}")
        if archived_selection_path:
            print("  ♻️ Selected archived counterpart:")
            print(f"     {archived_selection_path}")
        else:
            print(f"  🎯 Selected: {selected_path or '-'}")
        print(f"  🛠 Implement: {implement_step or '-'}")
        verification_label = verification_status or "not_run"
        if verification_label.startswith("failed:") and verification_failed_command:
            verification_label = f"failed ({verification_failed_command})"
        print(f"  🧪 Verify: {verification_label}")
        reviewer_label = reviewer_status or "not_run"
        if reviewer_decision:
            reviewer_label = f"{reviewer_label} ({reviewer_decision})"
        if failed_reviewer_id:
            reviewer_label = f"{reviewer_label} [{failed_reviewer_id}]"
        print(f"  👀 Reviewer: {reviewer_label}")
        if result == "passed":
            print(f"  {presenter.format_iteration_passed_line()}")
        else:
            print(f"  {presenter.format_iteration_failed_line(failed_gate)}")
            if log_path:
                print(f"  📄 Log: {log_path}")
        print(f"  ➡️ Next: {next_action}")

    print(
        "Loop summary: "
        f"result={result} feature={feature_id or '-'} "
        f"attempt={attempt if attempt is not None else '-'} next={next_action}"
        f"{presenter.format_summary_suffix(result)}"
    )
    if failed_gate:
        print(presenter.format_failed_gate_line(failed_gate))


def _iteration_cap_reached(total_iterations: int, max_iterations: int) -> bool:
    if total_iterations >= max_iterations:
        print(f"Reached max iteration cap ({max_iterations}) before completion.")
        return True
    return False


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
    pending = _pending_features(resolved_paths)
    if pending:
        return pending

    done_pending_archive = _done_features_pending_archive(resolved_paths)
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
        if outcome.hook_feedback:
            print(f"Detail: {outcome.hook_feedback}")
        return 1

    return None


def _run_feature_iteration(
    project_root: Path,
    feature_path: Path,
    run_all: bool,
    attempt: int,
    hook_feedback: str | None,
    verbose_output: bool,
    opencode_prompt: str | None = None,
) -> IterationOutcome:
    del opencode_prompt  # back-compat signature; intentionally unused
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        run_all=run_all,
        attempt=attempt,
        hook_feedback=hook_feedback,
        verbose_output=verbose_output,
    )
    return _run_feature_iteration_with_inputs(iteration_inputs)


def _run_feature_iteration_with_inputs(
    iteration_inputs: FeatureIterationInputs,
) -> IterationOutcome:
    return run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=_evaluate_initial_feature_load,
            ready_for_active_iteration=(
                lambda result, feature, loaded_from_archive: (
                    _ready_for_active_iteration(
                        result=result,
                        feature=feature,
                        loaded_from_archive=loaded_from_archive,
                    )
                )
            ),
            touch_active_feature_for_iteration=_touch_active_feature_for_iteration,
            run_implement_step=run_implement_step,
            refresh_feature_after_implement=(
                lambda project_root, feature_path, selected_started_active: (
                    _refresh_feature_after_implement(
                        project_root,
                        feature_path,
                        selected_started_active=selected_started_active,
                    )
                )
            ),
            should_archive_selected_feature=(
                lambda result, selected_feature, loaded_from_archive: (
                    _should_archive_selected_feature(
                        result=result,
                        selected_feature=selected_feature,
                        loaded_from_archive=loaded_from_archive,
                    )
                )
            ),
            archive_completed_feature=_archive_completed_feature,
            run_gate_phase=run_gate_phase,
            gate_phase_dependencies=GatePhaseDependencies(
                restore_archived_feature=_restore_archived_feature,
                collect_changed_paths=collect_changed_paths,
                run_shell_command=run_shell_command,
            ),
            run_verification_phase=run_verification_phase,
            verification_phase_dependencies=VerificationPhaseDependencies(
                run_shell_command=run_shell_command,
            ),
            run_reviewer_phase=run_reviewer_phase,
            reviewer_phase_dependencies=ReviewerPhaseDependencies(
                collect_changed_paths=collect_changed_paths,
                restore_archived_feature=_restore_archived_feature,
                start_agent=start_agent,
            ),
            run_completion_commit_phase=run_completion_commit_phase,
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=_commit_feature_completion,
                restore_archived_feature=_restore_archived_feature,
            ),
            write_iteration_telemetry=write_iteration_telemetry,
            git_head_resolver=git_head_short,
            print_summary=print_summary,
        ),
    )


def _resolve_run_targets(
    project_root: Path,
    feature_paths: Sequence[str | Path],
    run_all: bool,
) -> list[Path]:
    if run_all:
        return _discover_active_feature_paths(project_root)
    return _resolve_feature_paths(project_root, feature_paths)


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

    pending = _pending_features(resolved_paths)
    if not pending:
        if run_all:
            _print_run_all_no_work_message()
        else:
            print("No pending features found in provided paths.")
            print_summary(None, "dry_run", None, None, "stop")
        return 0

    if run_all:
        print("[dry-run] Selection is taken from the startup snapshot (no rescan).")
    feature_path, feature = deterministic_feature_choice(pending)
    fid = str(feature.get("id", ""))
    print(f"[dry-run] Resolved {len(resolved_paths)} feature file(s).")
    print(f"[dry-run] Selected feature={fid} path={feature_path}")
    print_summary(fid, "dry_run", None, None, "stop")
    return 0


def _enforce_worktree_precondition(
    project_root: Path,
    allow_dirty: bool,
) -> int | None:
    proc = status_porcelain(project_root)
    if proc.returncode != 0:
        reason = "unable to read git status; run inside a git repository"
        print(f"Precondition failed: {reason}")
        print("Hint: run from inside a git repository (try `git init`).")
        return 1

    dirty = bool(proc.stdout.strip())
    if not dirty:
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


_require_clean_worktree = (
    _enforce_worktree_precondition  # Back-compat monkeypatch seam.
)


def _run_selected_feature_iterations(
    loop_run: LoopRun,
) -> int:
    config = loop_run.config
    state = loop_run.state

    while True:
        resolved_paths = list(state.resolved_feature_paths)
        pending = _runnable_feature_candidates(
            resolved_paths,
        )
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
            outcome = _run_feature_iteration(
                project_root=config.project_root,
                feature_path=selected_feature_path,
                run_all=config.run_all,
                attempt=state.total_iterations,
                hook_feedback=state.feedback_for(selected_feature_path),
                verbose_output=config.verbose_output,
            )

            state = state.with_retry_feedback(
                selected_feature_path,
                outcome.hook_feedback,
            )

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


class RunConfigOptions(NamedTuple):
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


def build_loop_run(config: RunConfig) -> LoopRun:
    """Build the default loop runtime context from run configuration."""
    services = RunServices(
        resolve_run_targets=_resolve_run_targets,
        emit_run_all_snapshot_feedback=_emit_run_all_snapshot_feedback,
        handle_dry_run=_handle_dry_run,
        enforce_worktree_precondition=_enforce_worktree_precondition,
        run_permission_precheck=_run_opencode_permission_precheck,
        run_selected_feature_iterations=_run_selected_feature_iterations,
    )
    return LoopRun(config=config, services=services)


def run_loop(loop_run: LoopRun) -> int:
    """Execute feature loops from a typed loop context."""
    return run_loop_controller(loop_run)
