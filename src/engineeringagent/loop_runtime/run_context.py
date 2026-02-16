"""Typed run-context models for loop orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from pydantic import BaseModel, ConfigDict, Field


class RunConfig(BaseModel):
    """Immutable run configuration carried through orchestration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_paths: tuple[str | Path, ...]
    gate_profile: str
    dry_run: bool
    run_all: bool = False
    max_iterations: int = 50
    allow_dirty: bool = False
    verbose_output: bool = False


class RunServices(BaseModel):
    """Immutable dependency bundle for loop runtime orchestration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resolve_run_targets: Callable[[Path, Sequence[str | Path], bool], list[Path]]
    emit_run_all_snapshot_feedback: Callable[[Sequence[Path], bool], int | None]
    handle_dry_run: Callable[[Sequence[Path], bool, bool], int | None]
    enforce_worktree_precondition: Callable[[Path, bool], int | None]
    run_permission_precheck: Callable[..., bool]
    run_selected_feature_iterations: Callable[[LoopRun], int]


class RunState(BaseModel):
    """Copy-on-write loop state tracked across iterations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_iterations: int = 0
    resolved_feature_paths: tuple[Path, ...] = Field(default_factory=tuple)
    retry_feedback_by_path: tuple[tuple[Path, str], ...] = Field(default_factory=tuple)

    def feedback_for(self, feature_path: Path) -> str | None:
        """Return retry feedback associated with one feature path."""
        return dict(self.retry_feedback_by_path).get(feature_path)

    def with_retry_feedback(
        self,
        feature_path: Path,
        hook_feedback: str | None,
    ) -> RunState:
        """Return a copied state with one retry feedback update."""
        feedback_by_path = dict(self.retry_feedback_by_path)
        if hook_feedback is None:
            feedback_by_path.pop(feature_path, None)
        else:
            feedback_by_path[feature_path] = hook_feedback
        return self.model_copy(
            update={"retry_feedback_by_path": tuple(feedback_by_path.items())}
        )

    def with_resolved_feature_paths(
        self,
        resolved_feature_paths: Sequence[Path],
    ) -> RunState:
        """Return a copied state with new resolved feature path snapshot."""
        return self.model_copy(
            update={"resolved_feature_paths": tuple(resolved_feature_paths)}
        )

    def increment_total_iterations(self) -> RunState:
        """Return a copied state with iteration counter incremented."""
        return self.model_copy(update={"total_iterations": self.total_iterations + 1})


class LoopRun(BaseModel):
    """Single pass-around runtime context for loop orchestration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: RunConfig
    services: RunServices
    state: RunState = Field(default_factory=RunState)

    def with_state(self, state: RunState) -> LoopRun:
        """Return a copied loop context with updated state."""
        return self.model_copy(update={"state": state})
