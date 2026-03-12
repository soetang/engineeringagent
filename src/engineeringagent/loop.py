from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple, Sequence

from .adapters.progress import write_iteration_telemetry
from .adapters.runtime.execution import run_loop_controller
from .adapters.runtime.loop_run_context import LoopRun, RunConfig, RunServices
from .adapters.runtime.feature_selector import choose_feature_with_selector
from .agents import preflight, run_agent
from .application import FeatureIterationRequest
from .domain.audit import (
    FeatureIterationInputs,
    IterationOutcome,
    IterationReport,
    IterationSummaryInputs,
)
from .bootstrap import AppFactory
from .bootstrap import runtime_support as _runtime_support
from .bootstrap.iteration_reporting import (
    DefaultObserverDependencies,
    IterationReportObserver,
    build_default_iteration_report_observers,
    publish_iteration_report,
)
from .domain.specification import feature_completion_commit_subject
from .domain.specification import deterministic_feature_choice
from .loop_runtime.feature_state import (
    discover_active_feature_paths,
    done_features_pending_archive,
    pending_features,
    resolve_feature_paths,
)
from .ports import CommitRequest, VersionControlFailure, VersionControlGateway

__all__ = ["run_loop_controller"]

print_summary = _runtime_support.print_summary
run_implement_step = _runtime_support.run_implement_step


def git_head_short(project_root: Path) -> str | None:
    """Return the short git HEAD hash for a repository."""
    return _build_version_control_gateway(project_root).head_commit(project_root)


def _print_run_all_snapshot_banner(resolved_paths: Sequence[Path]) -> None:
    print(
        "[run --all] Startup snapshot captured "
        f"{len(resolved_paths)} runnable feature entrypoint(s) from docs/spec/features/."
    )


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


def _build_version_control_gateway(project_root: Path) -> VersionControlGateway:
    return AppFactory(project_root).build_version_control_gateway()


def _commit_feature_completion(
    project_root: Path, feature: dict[str, Any]
) -> tuple[bool, str | None, str]:
    message = feature_completion_commit_subject(feature)
    commit_result = _build_version_control_gateway(project_root).commit(
        CommitRequest(
            workspace_path=project_root,
            message=message,
            stage_all=True,
            allow_empty=False,
        )
    )
    output = commit_result.stdout + commit_result.stderr
    if commit_result.commit_created:
        return (True, None, output)
    return (False, commit_result.failure_stage, output)


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


def _run_feature_iteration(
    project_root: Path,
    feature_path: Path,
    run_all: bool,
    attempt: int,
    feedback: str | None,
    verbose_output: bool,
) -> IterationOutcome:
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        run_all=run_all,
        attempt=attempt,
        feedback=feedback,
        verbose_output=verbose_output,
    )
    result = AppFactory(project_root).build_feature_iteration_service().run(
        FeatureIterationRequest(
            project_root=iteration_inputs.project_root,
            feature_path=iteration_inputs.feature_path,
            run_all=iteration_inputs.run_all,
            attempt=iteration_inputs.attempt,
            feedback=iteration_inputs.feedback,
            verbose_output=iteration_inputs.verbose_output,
        )
    )
    return IterationOutcome.model_validate(result.model_dump())


def _default_iteration_report_observers() -> tuple[IterationReportObserver, ...]:
    return build_default_iteration_report_observers(
        DefaultObserverDependencies(
            write_iteration_telemetry=(
                lambda telemetry_inputs: write_iteration_telemetry(
                    telemetry_inputs,
                    git_head_resolver=git_head_short,
                )
            ),
            persist_iteration_report=_persist_iteration_report,
            git_head_resolver=git_head_short,
            print_summary=print_summary,
        )
    )


def _persist_iteration_report(report: IterationReport) -> None:
    AppFactory(
        report.telemetry_inputs.iteration_inputs.project_root
    ).build_progress_journal().write_iteration_report(
        project_root=report.telemetry_inputs.iteration_inputs.project_root,
        feature_id=report.feature_id,
        payload=report.model_dump(mode="json"),
    )


def _publish_iteration_report(
    report: IterationReport,
    *,
    observers: Sequence[IterationReportObserver] | None = None,
) -> IterationOutcome:
    active_observers = (
        tuple(observers)
        if observers is not None
        else _default_iteration_report_observers()
    )
    published_report = publish_iteration_report(report, active_observers)
    return IterationOutcome.from_report(published_report)


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
    fid = str(feature.get("id", ""))
    print(f"[dry-run] Resolved {len(resolved_paths)} feature file(s).")
    print(f"[dry-run] Selected feature={fid} path={feature_path}")
    print_summary(
        IterationSummaryInputs(
            feature_id=fid,
            result="dry_run",
            failed_gate=None,
            attempt=None,
            next_action="stop",
        )
    )
    return 0


def _enforce_worktree_precondition(
    project_root: Path,
    allow_dirty: bool,
) -> int | None:
    try:
        status = _build_version_control_gateway(project_root).worktree_status(project_root)
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
                feedback=state.feedback_for(selected_feature_path),
                verbose_output=config.verbose_output,
            )

            state = state.with_feedback(
                selected_feature_path,
                outcome.feedback,
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
            if _iteration_cap_reached_after_failure(
                outcome,
                total_iterations=state.total_iterations,
                max_iterations=config.max_iterations,
            ):
                return 1


class RunConfigOptions(NamedTuple):
    """Scalar CLI options used to build a typed `RunConfig`.

    This is intentionally a small, immutable container so the CLI can collect
    flags/options without threading a full `RunConfig` through Typer parsing.
    """

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
        run_permission_precheck=preflight,
        run_selected_feature_iterations=_run_selected_feature_iterations,
    )
    return LoopRun(config=config, services=services)
