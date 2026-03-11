"""Runtime execution adapters for transitional loop orchestration."""

from .execution import RuntimeFeatureIterationExecutor, RuntimeRunLoopExecutor
from .run_loop_builder import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
    enforce_worktree_precondition,
    run_selected_feature_iterations,
)
from .run_loop_context import LoopRun, RunConfig, RunServices, RunState

__all__ = [
    "LoopRun",
    "RunConfig",
    "RunConfigOptions",
    "RunServices",
    "RunState",
    "RuntimeFeatureIterationExecutor",
    "RuntimeRunLoopExecutor",
    "build_loop_run",
    "build_run_config",
    "enforce_worktree_precondition",
    "run_selected_feature_iterations",
]
