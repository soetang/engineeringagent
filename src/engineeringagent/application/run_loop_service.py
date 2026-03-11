"""Application service for run-loop execution requests."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict


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


LoadHarnessChecksDocument = Callable[
    [Path],
    tuple[object | None, str | None],
]
ExecuteRunLoop = Callable[[RunLoopRequest], int]


class RunLoopService:
    """Owns run-loop input validation and preflight checks."""

    def __init__(
        self,
        *,
        load_harness_checks_document: LoadHarnessChecksDocument,
        execute_run_loop: ExecuteRunLoop,
    ) -> None:
        self._load_harness_checks_document = load_harness_checks_document
        self._execute_run_loop = execute_run_loop

    def run(self, request: RunLoopRequest) -> RunLoopResult:
        """Execute one run-loop request after deterministic preflight."""
        input_error = self._validate_input(request)
        if input_error is not None:
            return RunLoopResult(exit_code=1, message=input_error)

        if request.run_all:
            _, checks_error = self._load_harness_checks_document(request.project_root)
            if checks_error is not None:
                return RunLoopResult(exit_code=1, message=checks_error)

        return RunLoopResult(exit_code=self._execute_run_loop(request))

    def _validate_input(self, request: RunLoopRequest) -> str | None:
        if request.run_all and request.feature_paths:
            return "run input error: positional feature paths cannot be used with --all"
        if not request.run_all and not request.feature_paths:
            return "run input error: provide one or more feature paths, or use --all"
        return None
