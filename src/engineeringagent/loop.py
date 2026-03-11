from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple, Sequence

from .changed_paths import collect_changed_paths
from .agents import preflight, run_agent
from .bootstrap import AppFactory
from .loop_runtime.controller import run_loop_controller
from .loop_runtime.implement import run_implement_step_from_inputs
from .loop_runtime.models import (
    FeatureIterationInputs,
    ImplementStepResult,
    ImplementStepInputs,
    IterationOutcome,
    IterationReport,
    IterationSummaryInputs,
)
from .loop_runtime.iteration import (
    IterationPipelineDependencies,
    run_feature_iteration_pipeline,
)
from .loop_runtime.phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
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
    archive_completed_feature,
    discover_active_feature_paths,
    done_features_pending_archive,
    evaluate_initial_feature_load,
    pending_features,
    ready_for_active_iteration,
    refresh_feature_after_implement,
    resolve_feature_paths,
    restore_archived_feature,
    should_archive_selected_feature,
    touch_active_feature_for_iteration,
)
from .loop_runtime.run_context import LoopRun, RunConfig, RunServices
from .loop_runtime.observers import (
    DefaultObserverDependencies,
    IterationReportObserver,
    build_default_iteration_report_observers,
    publish_iteration_report,
)
from .loop_runtime.telemetry import write_iteration_telemetry
from .presentation.presenters.terminal import RunOutputPresenter
from .feature_commit import feature_completion_commit_subject
from .ports import CommitRequest, VersionControlFailure, VersionControlGateway
from .specs import progress_kind_label

__all__ = ["run_loop_controller"]


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


def _choose_feature_with_selector(
    project_root: Path,
    pending: Sequence[tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    app_factory = AppFactory(project_root)
    return choose_feature_with_selector(
        project_root,
        pending,
        build_selector_prompt_fn=app_factory.build_prompt_builder().build_selector_prompt,
        run_agent_fn=run_agent,
    )


def _build_version_control_gateway(project_root: Path) -> VersionControlGateway:
    return AppFactory(project_root).build_version_control_gateway()


def git_head_short(project_root: Path) -> str | None:
    """Return short git HEAD hash for a repository.

    Args:
        project_root: Repository root used as command cwd.

    Returns:
        Short commit hash when available, otherwise None.
    """
    return _build_version_control_gateway(project_root).head_commit(project_root)


def run_implement_step(
    project_root: Path,
    feature: dict[str, Any],
    feature_path: Path,
    feedback: str | None,
    verbose_output: bool,
) -> ImplementStepResult:
    """Run the implement phase for one loop iteration."""
    app_factory = AppFactory(project_root)
    implement_inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature,
        feature_path=feature_path,
        feedback=feedback,
        verbose_output=verbose_output,
    )
    return run_implement_step_from_inputs(
        implement_inputs,
        agent_runner=app_factory.build_agent_runner(),
        prompt_builder=app_factory.build_prompt_builder(),
        progress_journal=app_factory.build_progress_journal(),
    )


def _commit_feature_completion(
    project_root: Path, feature: dict[str, Any]
) -> tuple[bool, str | None, str]:
    message = feature_completion_commit_subject(feature)
    commit_result = _build_version_control_gateway(project_root).commit(
        CommitRequest(
            project_root=project_root,
            message=message,
            stage_all=True,
            allow_empty=False,
        )
    )
    output = commit_result.stdout + commit_result.stderr
    if commit_result.commit_created:
        return (True, None, output)
    return (False, commit_result.failure_stage, output)


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
    return _run_feature_iteration_with_inputs(iteration_inputs)


def _run_feature_iteration_with_inputs(
    iteration_inputs: FeatureIterationInputs,
) -> IterationOutcome:
    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=evaluate_initial_feature_load,
            ready_for_active_iteration=ready_for_active_iteration,
            touch_active_feature_for_iteration=touch_active_feature_for_iteration,
            run_implement_step=run_implement_step,
            refresh_feature_after_implement=refresh_feature_after_implement,
            should_archive_selected_feature=should_archive_selected_feature,
            archive_completed_feature=archive_completed_feature,
            run_gate_phase=run_gate_phase,
            gate_phase_dependencies=GatePhaseDependencies(
                restore_archived_feature=restore_archived_feature,
                collect_changed_paths=collect_changed_paths,
            ),
            run_verification_phase=run_verification_phase,
            run_reviewer_phase=run_reviewer_phase,
            reviewer_phase_dependencies=ReviewerPhaseDependencies(
                collect_changed_paths=collect_changed_paths,
                restore_archived_feature=restore_archived_feature,
            ),
            run_completion_commit_phase=run_completion_commit_phase,
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=_commit_feature_completion,
                restore_archived_feature=restore_archived_feature,
            ),
        ),
    )
    return _publish_iteration_report(report)


def _default_iteration_report_observers() -> tuple[IterationReportObserver, ...]:
    return build_default_iteration_report_observers(
        DefaultObserverDependencies(
            write_iteration_telemetry=(
                lambda telemetry_inputs, git_head_resolver: write_iteration_telemetry(
                    telemetry_inputs,
                    git_head_resolver=git_head_resolver,
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
