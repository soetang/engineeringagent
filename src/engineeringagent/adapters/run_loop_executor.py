"""Run-loop execution adapters."""

from __future__ import annotations

from importlib import import_module

from engineeringagent.ports import RunLoopExecutionRequest, RunLoopExecutor


class LegacyLoopRunLoopExecutor(RunLoopExecutor):
    """Bridge the application run-loop service to the legacy loop facade."""

    def run(self, request: RunLoopExecutionRequest) -> int:
        """Execute the legacy loop facade behind a port boundary."""
        loop_module = import_module("engineeringagent.loop")
        config = loop_module.build_run_config(
            project_root=request.project_root,
            feature_paths=request.feature_paths,
            options=loop_module.RunConfigOptions(
                request.dry_run,
                request.run_all,
                request.max_iterations,
                request.allow_dirty,
                request.verbose_output,
            ),
        )
        loop_run = loop_module.build_loop_run(config)
        return loop_module.run_loop_controller(loop_run)
