"""Application service for run-loop execution requests."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.ports import (
    ChecksCatalogRepository,
    RunLoopExecutionRequest,
    RunLoopExecutor,
    ValidationFailure,
)


class RunLoopRequest(BaseModel):
    """Typed input for one run-loop execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_paths: tuple[str | Path, ...]
    run_all: bool
    dry_run: bool
    max_iterations: int
    allow_dirty: bool
    verbose_output: bool


class RunLoopResult(BaseModel):
    """Stable application result for one run-loop execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exit_code: int
    message: str | None = None


class RunLoopService:
    """Owns run-loop input validation and preflight checks."""

    def __init__(
        self,
        *,
        checks_catalog_repository: ChecksCatalogRepository,
        executor: RunLoopExecutor,
    ) -> None:
        self._checks_catalog_repository = checks_catalog_repository
        self._executor = executor

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

        return RunLoopResult(
            exit_code=self._executor.run(self._to_execution_request(request))
        )

    def _validate_input(self, request: RunLoopRequest) -> str | None:
        if request.run_all and request.feature_paths:
            return "run input error: positional feature paths cannot be used with --all"
        if not request.run_all and not request.feature_paths:
            return "run input error: provide one or more feature paths, or use --all"
        return None

    def _to_execution_request(
        self,
        request: RunLoopRequest,
    ) -> RunLoopExecutionRequest:
        return RunLoopExecutionRequest(
            project_root=request.project_root,
            feature_paths=request.feature_paths,
            run_all=request.run_all,
            dry_run=request.dry_run,
            max_iterations=request.max_iterations,
            allow_dirty=request.allow_dirty,
            verbose_output=request.verbose_output,
        )
