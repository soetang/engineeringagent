"""Guidance-domain topic model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GuidanceTopic(BaseModel):
    """Stable guidance topic content and metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_id: str
    aliases: tuple[str, ...]
    title: str
    description: str | None
    document: str | None
    body: str | None
