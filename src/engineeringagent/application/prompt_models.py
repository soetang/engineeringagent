"""Application-owned prompt assembly contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PromptArtifactPaths(BaseModel):
    """Explicit prompt artifact references resolved before rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    specification: Path
    plan: str | None = None
    research: str | None = None


PromptProgressKind = Literal["phase", "feature"]


class ImplementationPromptFeature(BaseModel):
    """Explicit feature fields allowed into the implementation prompt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: str
    title: str = ""
    objective: str = ""
    context: str = ""


class ImplementationPromptRequest(BaseModel):
    """Typed input for implementation prompt rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: ImplementationPromptFeature
    artifacts: PromptArtifactPaths
    handoff_path: str | None
    feedback: str | None
    progress_kind: PromptProgressKind
    current_progress: str | None = None
