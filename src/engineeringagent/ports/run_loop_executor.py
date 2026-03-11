"""Port contract for run-loop execution."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class RunLoopExecutionRequest(BaseModel):
    """Typed run-loop execution request passed to infrastructure adapters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_paths: tuple[str | Path, ...]
    dry_run: bool
    run_all: bool
    max_iterations: int
    allow_dirty: bool
    verbose_output: bool


class RunLoopExecutor(Protocol):
    """Execute the configured loop runtime for one request."""

    def run(self, request: RunLoopExecutionRequest) -> int:
        """Return the loop process exit code."""
        raise NotImplementedError
