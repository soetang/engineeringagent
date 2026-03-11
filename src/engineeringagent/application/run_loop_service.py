"""Application service for run-loop execution requests."""

from __future__ import annotations

from engineeringagent.application.contracts import (
    RunLoopRequest,
    RunLoopResult,
    RunLoopRuntime,
)
from engineeringagent.ports import (
    ChecksCatalogRepository,
    ValidationFailure,
)


class RunLoopService:
    """Owns run-loop input validation and preflight checks."""

    def __init__(
        self,
        *,
        checks_catalog_repository: ChecksCatalogRepository,
        runtime: RunLoopRuntime,
    ) -> None:
        self._checks_catalog_repository = checks_catalog_repository
        self._runtime = runtime

    def run(self, request: RunLoopRequest) -> RunLoopResult:
        """Execute one run-loop request after deterministic preflight."""
        input_error = self._validate_input(request)
        if input_error is not None:
            return RunLoopResult(exit_code=1, message=input_error)

        if request.run_all:
            try:
                self._checks_catalog_repository.load(request.project_root)
            except ValidationFailure as exc:
                return RunLoopResult(exit_code=1, message=exc.message)

        return RunLoopResult(exit_code=self._run(request))

    def _validate_input(self, request: RunLoopRequest) -> str | None:
        if request.run_all and request.feature_paths:
            return "run input error: positional feature paths cannot be used with --all"
        if not request.run_all and not request.feature_paths:
            return "run input error: provide one or more feature paths, or use --all"
        return None

    def _run(self, request: RunLoopRequest) -> int:
        config = self._runtime.build_run_config(
            project_root=request.project_root,
            feature_paths=request.feature_paths,
            options=self._runtime.config_options(
                request.dry_run,
                request.run_all,
                request.max_iterations,
                request.allow_dirty,
                request.verbose_output,
            ),
        )
        loop_run = self._runtime.build_loop_run(config)
        return self._runtime.run_loop_controller(loop_run)
