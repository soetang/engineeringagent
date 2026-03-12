"""Guidance-domain topic model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.shared import TopicId


class GuidanceTopic(BaseModel):
    """Stable guidance topic content and metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_id: TopicId
    aliases: tuple[str, ...]
    title: str
    description: str | None
    document: str | None
    body: str | None


class UnknownGuidanceTopicIdError(ValueError):
    """Raised when a guidance topic id or alias cannot be resolved."""
