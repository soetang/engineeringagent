"""Bootstrap assembly helpers."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .app_factory import AppFactory
    from .iteration_reporting import (
        ConsoleObserverDependencies,
        DefaultObserverDependencies,
        IterationReportObserver,
        TelemetryObserverDependencies,
        build_console_observer,
        build_default_iteration_report_observers,
        build_progress_artifact_observer,
        build_telemetry_observer,
        publish_iteration_report,
    )
    from .run_loop_builder import (
        RunConfigOptions,
        build_loop_run,
        build_run_config,
        enforce_worktree_precondition,
        run_selected_feature_iterations,
    )
    from .run_loop_context import LoopRun, RunConfig, RunServices, RunState
    from .runtime_execution import run_loop_controller

__all__ = [
    "AppFactory",
    "ConsoleObserverDependencies",
    "DefaultObserverDependencies",
    "IterationReportObserver",
    "TelemetryObserverDependencies",
    "build_console_observer",
    "build_default_iteration_report_observers",
    "build_progress_artifact_observer",
    "build_telemetry_observer",
    "publish_iteration_report",
    "LoopRun",
    "RunConfig",
    "RunConfigOptions",
    "RunServices",
    "RunState",
    "build_loop_run",
    "build_run_config",
    "enforce_worktree_precondition",
    "run_selected_feature_iterations",
    "run_loop_controller",
]

_ITERATION_REPORTING_EXPORTS = {
    "ConsoleObserverDependencies",
    "DefaultObserverDependencies",
    "IterationReportObserver",
    "TelemetryObserverDependencies",
    "build_console_observer",
    "build_default_iteration_report_observers",
    "build_progress_artifact_observer",
    "build_telemetry_observer",
    "publish_iteration_report",
}

_RUN_LOOP_EXPORTS = {
    "LoopRun",
    "RunConfig",
    "RunConfigOptions",
    "RunServices",
    "RunState",
    "build_loop_run",
    "build_run_config",
    "enforce_worktree_precondition",
    "run_selected_feature_iterations",
}


def __getattr__(name: str) -> Any:
    """Lazily expose bootstrap helpers without forcing the full composition root."""
    if name == "AppFactory":
        return import_module("engineeringagent.bootstrap.app_factory").AppFactory
    if name in _ITERATION_REPORTING_EXPORTS:
        return getattr(
            import_module("engineeringagent.bootstrap.iteration_reporting"),
            name,
        )
    if name in _RUN_LOOP_EXPORTS:
        module_name = (
            "engineeringagent.bootstrap.run_loop_context"
            if name in {"LoopRun", "RunConfig", "RunServices", "RunState"}
            else "engineeringagent.bootstrap.run_loop_builder"
        )
        return getattr(import_module(module_name), name)
    if name == "run_loop_controller":
        return import_module(
            "engineeringagent.bootstrap.runtime_execution"
        ).run_loop_controller
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
