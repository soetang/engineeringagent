"""Feature workspace management port for isolated iteration state."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from .failures import PortFailure


class FeatureWorkspaceFailure(PortFailure):
    """Raised when a workspace adapter cannot satisfy a request."""

    def __init__(self, message: str) -> None:
        super().__init__("FeatureWorkspaceManager", message)


class WorkspaceResetRequest(BaseModel):
    """Stable request envelope for one feature workspace reset attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_path: Path
    target_ref: str
    clean_untracked: bool = True


class WorkspaceResetResult(BaseModel):
    """Stable result envelope for one feature workspace reset attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reset_applied: bool
    head_commit: str | None
    stdout: str
    stderr: str
    failure_stage: str | None = None


class FeatureWorkspaceManager(Protocol):
    """Provide normalized feature workspace lifecycle operations."""

    def reset_to_last_accepted(
        self,
        request: WorkspaceResetRequest,
    ) -> WorkspaceResetResult:
        """Reset the feature workspace to the last accepted commit."""
        raise NotImplementedError
