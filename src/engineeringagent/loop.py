from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict

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
    VerificationPhaseDependencies,
    run_completion_commit_phase,
    run_gate_phase,
    run_verification_phase,
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
from .loop_runtime.facade_signatures import (
    PRINT_SUMMARY_SIGNATURE,
    RUN_FEATURE_ITERATION_SIGNATURE,
    RUN_IMPLEMENT_STEP_SIGNATURE,
    RUN_LOOP_SIGNATURE,
    bind_facade_call,
)
from .loop_runtime.controller import (
    RunLoopControllerDependencies,
    RunLoopControllerInputs,
    run_loop_controller,
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


class _SelectedFeatureIterationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_profile: str
    implement_command: str | None
    opencode_prompt: str | None
    skip_implement: bool
    max_iterations: int
    verbose_output: bool


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


def run_implement_step(*args: Any, **kwargs: Any) -> tuple[bool, str | None, str]:
    """Run the implement phase for one loop iteration.

    Args:
        *args: Positional arguments matching `RUN_IMPLEMENT_STEP_SIGNATURE`.
        **kwargs: Keyword arguments matching `RUN_IMPLEMENT_STEP_SIGNATURE`.
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
    bound = bind_facade_call(RUN_IMPLEMENT_STEP_SIGNATURE, args, kwargs)
    implement_inputs = ImplementStepInputs(**bound)
    return run_implement_step_from_inputs(
        implement_inputs,
        run_shell_command_fn=run_shell_command,
        start_agent_fn=start_agent,
    )


run_implement_step.__signature__ = RUN_IMPLEMENT_STEP_SIGNATURE


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


def print_summary(*args: Any, **kwargs: Any) -> None:
    """Print a one-line loop summary and optional gate failure.

    Args:
        *args: Positional arguments matching `PRINT_SUMMARY_SIGNATURE`.
        **kwargs: Keyword arguments matching `PRINT_SUMMARY_SIGNATURE`.
        feature_id: Feature identifier for reporting.
        result: Iteration result label.
        failed_gate: Failed gate name when iteration fails.
        attempt: Iteration attempt number.
        next_action: Suggested next loop action.
        selected_path: Selected active feature path for iteration display.
        implement_step: Implement step descriptor for iteration display.
        log_path: Optional per-feature log path for failed iterations.
        archived_selection_path: Archived counterpart path when selection moved.
        verification_status: Verification phase status for current iteration.
        verification_failed_command: Failed verification command when available.
    """
    bound = bind_facade_call(PRINT_SUMMARY_SIGNATURE, args, kwargs)
    feature_id = bound["feature_id"]
    result = bound["result"]
    failed_gate = bound["failed_gate"]
    attempt = bound["attempt"]
    next_action = bound["next_action"]
    selected_path = bound["selected_path"]
    implement_step = bound["implement_step"]
    log_path = bound["log_path"]
    archived_selection_path = bound["archived_selection_path"]
    verification_status = bound["verification_status"]
    verification_failed_command = bound["verification_failed_command"]

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


print_summary.__signature__ = PRINT_SUMMARY_SIGNATURE


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


def _run_feature_iteration(*args: Any, **kwargs: Any) -> IterationOutcome:
    bound = bind_facade_call(RUN_FEATURE_ITERATION_SIGNATURE, args, kwargs)
    iteration_inputs = FeatureIterationInputs(**bound)
    return _run_feature_iteration_with_inputs(iteration_inputs)


_run_feature_iteration.__signature__ = RUN_FEATURE_ITERATION_SIGNATURE


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
            run_verification_phase=run_verification_phase,
            verification_phase_dependencies=VerificationPhaseDependencies(
                run_shell_command=run_shell_command,
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
    clean, reason = _require_clean_worktree(project_root)
    if clean:
        return None
    if not allow_dirty:
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


def _run_selected_feature_iterations(
    project_root: Path,
    resolved_paths: list[Path],
    config: _SelectedFeatureIterationConfig,
) -> int:
    total_iterations = 0
    retry_feedback_by_path: dict[Path, str] = {}

    while True:
        pending = _pending_features(resolved_paths)
        if not pending:
            print("All provided features are done and committed.")
            return 0

        if _iteration_cap_reached(total_iterations, config.max_iterations):
            return 1

        selected_feature_path, selected_feature = _choose_feature_with_selector(
            project_root, pending
        )
        selected_feature_id = str(selected_feature.get("id", ""))
        print(f"Selected feature={selected_feature_id} path={selected_feature_path}")

        while True:
            if _iteration_cap_reached(total_iterations, config.max_iterations):
                return 1

            total_iterations += 1
            outcome = _run_feature_iteration(
                project_root=project_root,
                feature_path=selected_feature_path,
                gate_profile=config.gate_profile,
                implement_command=config.implement_command,
                opencode_prompt=config.opencode_prompt,
                skip_implement=config.skip_implement,
                attempt=total_iterations,
                hook_feedback=retry_feedback_by_path.get(selected_feature_path),
                verbose_output=config.verbose_output,
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


def run_loop(*args: Any, **kwargs: Any) -> int:
    """Execute feature loops until completion or termination condition.

    Args:
        *args: Positional arguments matching `RUN_LOOP_SIGNATURE`.
        **kwargs: Keyword arguments matching `RUN_LOOP_SIGNATURE`.
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
    inputs = RunLoopControllerInputs(
        **bind_facade_call(RUN_LOOP_SIGNATURE, args, kwargs)
    )

    def _make_iteration_config(
        controller_inputs: RunLoopControllerInputs,
    ) -> _SelectedFeatureIterationConfig:
        return _SelectedFeatureIterationConfig(
            gate_profile=controller_inputs.gate_profile,
            implement_command=controller_inputs.implement_command,
            opencode_prompt=controller_inputs.opencode_prompt,
            skip_implement=controller_inputs.skip_implement,
            max_iterations=controller_inputs.max_iterations,
            verbose_output=controller_inputs.verbose_output,
        )

    dependencies = RunLoopControllerDependencies(
        resolve_run_targets=_resolve_run_targets,
        emit_run_all_snapshot_feedback=_emit_run_all_snapshot_feedback,
        handle_dry_run=_handle_dry_run,
        enforce_worktree_precondition=_enforce_worktree_precondition,
        run_permission_precheck=_run_opencode_permission_precheck,
        make_iteration_config=_make_iteration_config,
        run_selected_feature_iterations=_run_selected_feature_iterations,
    )
    return run_loop_controller(inputs, dependencies)


run_loop.__signature__ = RUN_LOOP_SIGNATURE
