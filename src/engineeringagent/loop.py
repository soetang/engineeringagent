from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .gates import load_gate_config, run_profile
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
    run_completion_commit_phase,
    run_gate_phase,
)
from .loop_runtime.selection import (
    choose_feature_with_selector,
    deterministic_feature_choice,
)
from .loop_runtime.feature_state import (
    _archive_completed_feature,
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
from .loop_runtime.telemetry import write_iteration_telemetry
from .loop_runtime.presentation import RunOutputPresenter

FEATURE_TYPE_COMMIT_PREFIX: dict[str, str] = {
    "feature": "feat",
    "bug": "fix",
    "spec": "spec",
    "docs": "docs",
    "chore": "chore",
    "test": "test",
}


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
    implement_command: str | None,
    skip_implement: bool,
) -> bool:
    return run_opencode_permission_precheck(
        project_root=project_root,
        implement_command=implement_command,
        skip_implement=skip_implement,
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


def run_implement_step(  # noqa: PLR0913 - compatibility seam for tests; delegates via ImplementStepInputs.
    project_root: Path,
    feature: dict[str, Any],
    feature_path: Path,
    implement_command: str | None,
    opencode_prompt: str | None,
    skip_implement: bool,
    hook_feedback: str | None,
    verbose_output: bool,
) -> tuple[bool, str | None, str]:
    """Run the implement phase for one loop iteration.

    Args:
        project_root: Repository root used for command execution.
        feature: Loaded feature mapping.
        feature_path: Path to feature YAML used in prompt generation.
        implement_command: Optional custom shell command override.
        opencode_prompt: Optional prompt override for OpenCode execution.
        skip_implement: Whether to skip implementation and run gates only.
        hook_feedback: Optional previous hook output to address on retry.
        verbose_output: Whether run-loop should stream full command output.

    Returns:
        Tuple of success flag, failure code, and combined command output.
    """
    implement_inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature,
        feature_path=feature_path,
        implement_command=implement_command,
        opencode_prompt=opencode_prompt,
        skip_implement=skip_implement,
        hook_feedback=hook_feedback,
        verbose_output=verbose_output,
    )
    return run_implement_step_from_inputs(
        implement_inputs,
        run_shell_command_fn=run_shell_command,
        start_agent_fn=start_agent,
    )


def _require_clean_worktree(project_root: Path) -> tuple[bool, str]:
    proc = status_porcelain(project_root)
    if proc.returncode != 0:
        return (False, "unable to read git status; run inside a git repository")
    if proc.stdout.strip():
        return (False, "working tree must be clean before running automated loop")
    return (True, "")


def _commit_feature_completion(
    project_root: Path, feature: dict[str, Any]
) -> tuple[bool, str | None, str]:
    message = _feature_completion_commit_subject(feature)

    add_proc = add_all(project_root)
    if add_proc.returncode != 0:
        output = (add_proc.stdout or "") + (add_proc.stderr or "")
        return (False, "git_add", output)

    commit_proc = git_commit(project_root, message)
    output = (commit_proc.stdout or "") + (commit_proc.stderr or "")
    if commit_proc.returncode == 0:
        return (True, None, output)
    return (False, "git_commit", output)


def _feature_completion_commit_subject(feature: dict[str, Any]) -> str:
    expected_subject = str(feature.get("expected_commit_subject", "")).strip()
    if expected_subject:
        return expected_subject

    fid = str(feature.get("id", "unknown-feature"))
    title = str(feature.get("title", "")).strip()
    feature_type = str(feature.get("type", "feature")).strip()
    prefix = FEATURE_TYPE_COMMIT_PREFIX.get(feature_type, "feat")
    message = f"{prefix}: complete {fid}"
    if title:
        message = f"{message} - {title}"
    return message


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
) -> None:
    """Print a one-line loop summary and optional gate failure.

    Args:
        feature_id: Feature identifier for reporting.
        result: Iteration result label.
        failed_gate: Failed gate name when iteration fails.
        attempt: Iteration attempt number.
        next_action: Suggested next loop action.
        selected_path: Selected active feature path for iteration display.
        implement_step: Implement step descriptor for iteration display.
        log_path: Optional per-feature log path for failed iterations.
        archived_selection_path: Archived counterpart path when selection moved.
    """
    presenter = RunOutputPresenter.for_current_terminal()
    if attempt is not None:
        print(f"🔁 Iteration {attempt} · {feature_id or '-'}")
        if archived_selection_path:
            print("  ♻️ Selected archived counterpart:")
            print(f"     {archived_selection_path}")
        else:
            print(f"  🎯 Selected: {selected_path or '-'}")
        print(f"  🛠 Implement: {implement_step or '-'}")
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


def _update_retry_feedback_for_feature(
    retry_feedback_by_path: dict[Path, str],
    selected_feature_path: Path,
    outcome: IterationOutcome,
) -> None:
    if outcome.hook_feedback:
        retry_feedback_by_path[selected_feature_path] = outcome.hook_feedback
        return
    retry_feedback_by_path.pop(selected_feature_path, None)


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


def _run_feature_iteration(  # noqa: PLR0913 - orchestration seam monkeypatched by loop tests.
    project_root: Path,
    feature_path: Path,
    gate_profile: str,
    implement_command: str | None,
    opencode_prompt: str | None,
    skip_implement: bool,
    attempt: int,
    hook_feedback: str | None,
    verbose_output: bool,
) -> IterationOutcome:
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        gate_profile=gate_profile,
        implement_command=implement_command,
        opencode_prompt=opencode_prompt,
        skip_implement=skip_implement,
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
                load_gate_config=load_gate_config,
                run_profile=run_profile,
                restore_archived_feature=_restore_archived_feature,
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


def run_loop(  # noqa: PLR0913 - public CLI facade signature must remain stable.
    project_root: Path,
    feature_paths: Sequence[str | Path],
    gate_profile: str,
    implement_command: str | None,
    opencode_prompt: str | None,
    skip_implement: bool,
    dry_run: bool,
    run_all: bool = False,
    max_iterations: int = 50,
    allow_dirty: bool = False,
    verbose_output: bool = False,
) -> int:
    """Execute feature loops until completion or termination condition.

    Args:
        project_root: Repository root for file and command operations.
        feature_paths: One or more feature spec file paths.
        gate_profile: Gate profile name to run after implementation.
        implement_command: Optional custom shell command for implementation.
        opencode_prompt: Optional prompt override for OpenCode implementation.
        skip_implement: Whether to skip implementation and run gates only.
        dry_run: Whether to resolve and report selection without execution.
        run_all: Whether to auto-discover active feature files.
        max_iterations: Max non-dry iterations across selected features.
        allow_dirty: Whether to permit non-dry execution with uncommitted changes.
        verbose_output: Whether to stream full implement and gate command output.

    Returns:
        Process exit code where 0 indicates success.
    """
    if max_iterations < 1:
        print("max_iterations must be >= 1")
        return 1

    try:
        if run_all:
            resolved_paths = _discover_active_feature_paths(project_root)
        else:
            resolved_paths = _resolve_feature_paths(project_root, feature_paths)
    except ValueError as exc:
        print(exc)
        return 1

    if run_all:
        _print_run_all_snapshot_banner(resolved_paths)
        if not resolved_paths:
            _print_run_all_no_work_message()
            return 0

    if dry_run:
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

    clean, reason = _require_clean_worktree(project_root)
    if not clean and not allow_dirty:
        print(f"Precondition failed: {reason}")
        print(
            "Hint: re-run with --allow-dirty to explicitly continue with "
            "uncommitted code changes."
        )
        return 1
    if not clean and allow_dirty:
        print(
            "Allow-dirty override enabled: continuing with uncommitted code "
            "changes by explicit user opt-in."
        )

    if not _run_opencode_permission_precheck(
        project_root=project_root,
        implement_command=implement_command,
        skip_implement=skip_implement,
    ):
        return 1

    total_iterations = 0
    retry_feedback_by_path: dict[Path, str] = {}

    while True:
        pending = _pending_features(resolved_paths)
        if not pending:
            print("All provided features are done and committed.")
            return 0

        if _iteration_cap_reached(total_iterations, max_iterations):
            return 1

        selected_feature_path, selected_feature = _choose_feature_with_selector(
            project_root, pending
        )
        selected_feature_id = str(selected_feature.get("id", ""))
        print(f"Selected feature={selected_feature_id} path={selected_feature_path}")

        while True:
            if _iteration_cap_reached(total_iterations, max_iterations):
                return 1

            total_iterations += 1
            outcome = _run_feature_iteration(
                project_root=project_root,
                feature_path=selected_feature_path,
                gate_profile=gate_profile,
                implement_command=implement_command,
                opencode_prompt=opencode_prompt,
                skip_implement=skip_implement,
                attempt=total_iterations,
                hook_feedback=retry_feedback_by_path.get(selected_feature_path),
                verbose_output=verbose_output,
            )

            _update_retry_feedback_for_feature(
                retry_feedback_by_path,
                selected_feature_path,
                outcome,
            )

            if outcome.completed:
                resolved_paths = _drop_completed_feature_from_snapshot(
                    resolved_paths,
                    selected_feature_path,
                )
                break

            terminal_failure_exit_code = _terminal_iteration_failure_exit_code(outcome)
            if terminal_failure_exit_code is not None:
                return terminal_failure_exit_code
