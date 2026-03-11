"""Adapter that delegates run-loop execution to the current runtime modules."""

from __future__ import annotations

from importlib import import_module

from engineeringagent.ports import RunLoopExecutionRequest


class RuntimeRunLoopExecutor:
    """Execute run-loop requests through the current runtime entrypoints."""

    def run(self, request: RunLoopExecutionRequest) -> int:
        """Build the runtime config and execute the loop controller."""
        loop_module = import_module("engineeringagent.loop")
        controller_module = import_module("engineeringagent.loop_runtime.controller")

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
        return controller_module.run_loop_controller(loop_run)
