"""Contracts for run-loop execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

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
