"""Run-loop adapter backed by the loop runtime package."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.application import FeatureIterationRequest
from engineeringagent.ports import RunLoopExecutionRequest, RunLoopExecutor
from engineeringagent.loop_runtime.controller import run_loop_controller
from engineeringagent.loop_runtime.models import FeatureIterationInputs, IterationOutcome
from engineeringagent.loop_runtime.run_context import LoopRun
from engineeringagent.loop_runtime.run_builder import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
    enforce_worktree_precondition,
    run_selected_feature_iterations,
)


class RuntimeRunLoopExecutor(RunLoopExecutor):
    """Execute run-loop requests through the loop runtime package."""

    def run(self, request: RunLoopExecutionRequest) -> int:
        """Build loop config and execute the runtime controller."""
        config = build_run_config(
            project_root=request.project_root,
            feature_paths=request.feature_paths,
            options=RunConfigOptions(
                request.dry_run,
                request.run_all,
                request.max_iterations,
                request.allow_dirty,
                request.verbose_output,
            ),
        )
        loop_run = build_loop_run(
            config,
            enforce_worktree_precondition_fn=self._enforce_worktree_precondition,
            run_selected_feature_iterations_fn=self._run_selected_feature_iterations,
        )
        return run_loop_controller(loop_run)

    def _enforce_worktree_precondition(
        self,
        project_root: Path,
        allow_dirty: bool,
    ) -> int | None:
        return enforce_worktree_precondition(
            project_root,
            allow_dirty,
            read_worktree_status=self._read_worktree_status,
        )

    def _read_worktree_status(self, project_root: Path) -> object:
        from engineeringagent.bootstrap import AppFactory

        return AppFactory(project_root).build_version_control_gateway().worktree_status(
            project_root
        )

    def _run_selected_feature_iterations(self, loop_run: LoopRun) -> int:
        return run_selected_feature_iterations(
            loop_run,
            run_feature_iteration=self._run_feature_iteration,
        )

    def _run_feature_iteration(
        self,
        iteration_inputs: FeatureIterationInputs,
    ) -> IterationOutcome:
        from engineeringagent.bootstrap import AppFactory

        result = AppFactory(
            iteration_inputs.project_root
        ).build_feature_iteration_service().run(
            FeatureIterationRequest(
                project_root=iteration_inputs.project_root,
                feature_path=iteration_inputs.feature_path,
                run_all=iteration_inputs.run_all,
                attempt=iteration_inputs.attempt,
                feedback=iteration_inputs.feedback,
                verbose_output=iteration_inputs.verbose_output,
            )
        )
        return IterationOutcome.model_validate(result.model_dump())
