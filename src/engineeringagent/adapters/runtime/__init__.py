"""Runtime execution adapters for transitional loop orchestration."""

from .execution import (
    RuntimeRunLoopExecutor,
    run_loop_controller,
)
from .iteration_phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    LoopTriggeredChecksRequest,
    ReviewerPhaseDependencies,
    run_completion_commit_phase,
    run_gate_phase,
    run_reviewer_phase,
    run_verification_phase,
)
from .loop_run_builder import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
    enforce_worktree_precondition,
    run_selected_feature_iterations,
)
from .loop_run_context import LoopRun, RunConfig, RunServices, RunState

__all__ = [
    "LoopRun",
    "LoopTriggeredChecksRequest",
    "RunConfig",
    "RunConfigOptions",
    "RunServices",
    "RunState",
    "CompletionPhaseDependencies",
    "GatePhaseDependencies",
    "ReviewerPhaseDependencies",
    "RuntimeRunLoopExecutor",
    "build_loop_run",
    "build_run_config",
    "enforce_worktree_precondition",
    "run_completion_commit_phase",
    "run_gate_phase",
    "run_loop_controller",
    "run_reviewer_phase",
    "run_selected_feature_iterations",
    "run_verification_phase",
]
