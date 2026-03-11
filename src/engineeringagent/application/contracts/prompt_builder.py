"""Contracts for prompt assembly."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ImplementationPromptRequest(BaseModel):
    """Typed input for implementation prompt rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: str
    specification_path: Path
    plan_path: str | None = None
    research_path: str | None = None
    handoff_path: str | None = None
    retry_feedback: str | None = None
