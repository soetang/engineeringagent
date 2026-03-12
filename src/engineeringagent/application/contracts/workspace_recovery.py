"""Contracts for deterministic workspace recovery."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class RecoverWorkspaceRequest(BaseModel):
    """Typed input for one workspace recovery request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_id: str
    last_accepted_commit: str
    require_handoff: bool = True


class RecoverWorkspaceResult(BaseModel):
    """Stable application result for one workspace recovery request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    head_commit: str | None
    handoff_path: Path | None
    message: str
