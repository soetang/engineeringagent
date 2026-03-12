"""Adapters that bridge application services to the loop runtime pipeline."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Callable

from engineeringagent.application import (
    FeatureIterationRequest,
    FeatureIterationService,
)
from engineeringagent.application.feature_iteration import (
    FeatureIterationInputs,
    IterationOutcome,
    IterationSummaryInputs,
)
from engineeringagent.ports import (
    RunLoopExecutionRequest,
    RunLoopExecutor,
    VersionControlGateway,
)
from .context import LoopRun
from .loop_run_builder import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
    enforce_worktree_precondition,
    run_selected_feature_iterations,
)

def run_loop_controller(loop_run: LoopRun) -> int:
    """Execute run-loop orchestration through the runtime adapter boundary."""
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

    if not services.run_permission_precheck(project_root=config.project_root):
        return 1

    state = loop_run.state.with_resolved_feature_paths(resolved_paths)
    return services.run_selected_feature_iterations(loop_run.with_state(state))


class RuntimeRunLoopExecutor(RunLoopExecutor):
    """Execute run-loop requests through the loop runtime package."""

    def __init__(
        self,
        *,
        build_feature_iteration_service: Callable[[Path], FeatureIterationService],
        build_version_control_gateway: Callable[[Path], VersionControlGateway],
    ) -> None:
        self._build_feature_iteration_service = build_feature_iteration_service
        self._build_version_control_gateway = build_version_control_gateway

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
            print_summary_fn=self._runtime_print_summary,
        )
        return run_loop_controller(loop_run)

    @staticmethod
    def _runtime_print_summary(summary: IterationSummaryInputs) -> None:
        runtime_support = import_module("engineeringagent.bootstrap.runtime_support")
        runtime_support.print_summary(summary)

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
        return self._build_version_control_gateway(project_root).worktree_status(
            project_root,
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
        result = self._build_feature_iteration_service(
            iteration_inputs.project_root
        ).run(
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
