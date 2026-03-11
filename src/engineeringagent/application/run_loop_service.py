"""Application service for run-loop execution requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from engineeringagent.ports import (
    ChecksCatalogRepository,
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


class RunLoopRuntime(BaseModel):
    """Legacy run-loop collaborators injected by bootstrap-owned wiring."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    config_options: Callable[..., Any]
    build_run_config: Callable[..., Any]
    build_loop_run: Callable[[Any], Any]
    run_loop_controller: Callable[[Any], int]


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
