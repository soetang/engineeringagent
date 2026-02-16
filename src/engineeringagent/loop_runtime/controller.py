"""Run-loop runtime controller orchestration interface."""

from __future__ import annotations

from .run_context import LoopRun


def run_loop_controller(
    loop_run: LoopRun,
) -> int:
    """Execute run-loop orchestration phases with injected boundaries."""
    config = loop_run.config
    services = loop_run.services

    if config.max_iterations < 1:
        print("max_iterations must be >= 1")
        return 1

    try:
        resolved_paths = services.resolve_run_targets(
            config.project_root,
            config.feature_paths,
            config.run_all,
        )
    except ValueError as exc:
        print(exc)
        return 1

    run_all_feedback_exit_code = services.emit_run_all_snapshot_feedback(
        resolved_paths,
        config.run_all,
    )
    if run_all_feedback_exit_code is not None:
        return run_all_feedback_exit_code

    dry_run_exit_code = services.handle_dry_run(
        resolved_paths,
        config.run_all,
        config.dry_run,
    )
    if dry_run_exit_code is not None:
        return dry_run_exit_code

    worktree_precondition_exit_code = services.enforce_worktree_precondition(
        config.project_root,
        config.allow_dirty,
    )
    if worktree_precondition_exit_code is not None:
        return worktree_precondition_exit_code

    if not services.run_permission_precheck(
        project_root=config.project_root,
        skip_implement=config.skip_implement,
    ):
        return 1

    state = loop_run.state.with_resolved_feature_paths(resolved_paths)
    return services.run_selected_feature_iterations(loop_run.with_state(state))
