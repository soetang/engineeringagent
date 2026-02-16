"""Run-loop runtime controller orchestration interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

from pydantic import BaseModel, ConfigDict


class RunLoopControllerInputs(BaseModel):
    """Bound facade inputs passed to the runtime controller."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_paths: Sequence[str | Path]
    gate_profile: str
    skip_implement: bool
    dry_run: bool
    run_all: bool
    max_iterations: int
    allow_dirty: bool
    verbose_output: bool


class RunLoopControllerDependencies(BaseModel):
    """Injectable dependency boundaries for run-loop orchestration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resolve_run_targets: Callable[[Path, Sequence[str | Path], bool], list[Path]]
    emit_run_all_snapshot_feedback: Callable[[Sequence[Path], bool], int | None]
    handle_dry_run: Callable[[Sequence[Path], bool, bool], int | None]
    enforce_worktree_precondition: Callable[[Path, bool], int | None]
    run_permission_precheck: Callable[..., bool]
    make_iteration_config: Callable[[RunLoopControllerInputs], Any]
    run_selected_feature_iterations: Callable[[Path, list[Path], Any], int]


def run_loop_controller(
    inputs: RunLoopControllerInputs,
    dependencies: RunLoopControllerDependencies,
) -> int:
    """Execute run-loop orchestration phases with injected boundaries."""
    if inputs.max_iterations < 1:
        print("max_iterations must be >= 1")
        return 1

    try:
        resolved_paths = dependencies.resolve_run_targets(
            inputs.project_root,
            inputs.feature_paths,
            inputs.run_all,
        )
    except ValueError as exc:
        print(exc)
        return 1

    run_all_feedback_exit_code = dependencies.emit_run_all_snapshot_feedback(
        resolved_paths,
        inputs.run_all,
    )
    if run_all_feedback_exit_code is not None:
        return run_all_feedback_exit_code

    dry_run_exit_code = dependencies.handle_dry_run(
        resolved_paths,
        inputs.run_all,
        inputs.dry_run,
    )
    if dry_run_exit_code is not None:
        return dry_run_exit_code

    worktree_precondition_exit_code = dependencies.enforce_worktree_precondition(
        inputs.project_root,
        inputs.allow_dirty,
    )
    if worktree_precondition_exit_code is not None:
        return worktree_precondition_exit_code

    if not dependencies.run_permission_precheck(
        project_root=inputs.project_root,
        skip_implement=inputs.skip_implement,
    ):
        return 1

    iteration_config = dependencies.make_iteration_config(inputs)
    return dependencies.run_selected_feature_iterations(
        inputs.project_root,
        resolved_paths,
        iteration_config,
    )
