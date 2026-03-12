"""Runtime execution adapters for transitional loop orchestration."""

from engineeringagent.application.run_loop import LoopRun, RunConfig, RunServices, RunState

from .execution import (
    RuntimeRunLoopExecutor,
    run_loop_controller,
)
from .feature_iteration_execution import (
    RuntimeFeatureIterationDependencies,
    RuntimeFeatureIterationExecutor,
    build_iteration_pipeline_dependencies,
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
    "RuntimeFeatureIterationDependencies",
    "RuntimeFeatureIterationExecutor",
    "RuntimeRunLoopExecutor",
    "build_iteration_pipeline_dependencies",
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
