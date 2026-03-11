"""Run-loop adapter backed by the legacy loop runtime module."""

from __future__ import annotations

from importlib import import_module

from engineeringagent.ports import RunLoopExecutionRequest, RunLoopExecutor


class RuntimeRunLoopExecutor(RunLoopExecutor):
    """Execute run-loop requests through the existing loop module."""

    def __init__(self) -> None:
        self._loop_module = import_module("engineeringagent.loop")

    def run(self, request: RunLoopExecutionRequest) -> int:
        """Build loop config and execute the runtime controller."""
        config = self._loop_module.build_run_config(
            project_root=request.project_root,
            feature_paths=request.feature_paths,
            options=self._loop_module.RunConfigOptions(
                request.dry_run,
                request.run_all,
                request.max_iterations,
                request.allow_dirty,
                request.verbose_output,
            ),
        )
        loop_run = self._loop_module.build_loop_run(config)
        return self._loop_module.run_loop_controller(loop_run)
