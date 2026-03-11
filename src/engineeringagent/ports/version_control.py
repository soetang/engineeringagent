"""Version-control port used by orchestration code."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from .failures import PortFailure


class VersionControlFailure(PortFailure):
    """Raised when a version-control adapter cannot satisfy a request."""

    def __init__(self, message: str) -> None:
        super().__init__("VersionControlGateway", message)


class CommitRequest(BaseModel):
    """Stable request envelope for one version-control commit attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    message: str
    stage_all: bool = True
    allow_empty: bool = False


class CommitResult(BaseModel):
    """Stable result envelope for one version-control commit attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    commit_created: bool
    commit_sha: str | None
    stdout: str
    stderr: str
    failure_stage: str | None = None


class DiffSummary(BaseModel):
    """Stable result envelope for one version-control diff query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_ref: str | None
    head_ref: str | None
    summary_text: str


class WorktreeStatus(BaseModel):
    """Stable result envelope for one worktree status query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dirty: bool
    stdout: str
    stderr: str


class VersionControlGateway(Protocol):
    """Provide normalized version-control operations to orchestration code."""

    def diff_against_base(
        self,
        project_root: Path,
        *,
        base_ref: str | None = None,
        head_ref: str | None = None,
    ) -> DiffSummary:
        """Return a diff summary for the selected revision range."""
        raise NotImplementedError

    def head_commit(self, project_root: Path) -> str | None:
        """Return the current short head commit, when available."""
        raise NotImplementedError

    def worktree_status(self, project_root: Path) -> WorktreeStatus:
        """Return the current worktree status for precondition checks."""
        raise NotImplementedError

    def commit(self, request: CommitRequest) -> CommitResult:
        """Create one deterministic commit and report the outcome."""
        raise NotImplementedError
