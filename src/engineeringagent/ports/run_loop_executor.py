"""Run-loop execution port used by the application layer."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class RunLoopExecutionRequest(BaseModel):
    """Stable request envelope for one run-loop execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_paths: tuple[str | Path, ...]
    run_all: bool
    dry_run: bool
    max_iterations: int
    allow_dirty: bool
    verbose_output: bool


class RunLoopExecutor(Protocol):
    """Execute the run loop without exposing runtime module details."""

    def run(self, request: RunLoopExecutionRequest) -> int:
        """Execute one normalized run-loop request."""
        raise NotImplementedError
