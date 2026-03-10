"""Guidance topic repository port."""

from __future__ import annotations

from typing import Protocol

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


class GuidanceTopicRepository(Protocol):
    """Load discoverable guidance topics and rendered topic bodies."""

    def list_topics(self) -> tuple[GuidanceTopic, ...]:
        """Return available guidance topics in stable display order."""
        raise NotImplementedError

    def load(self, topic_id: str) -> GuidanceTopic:
        """Return one guidance topic by canonical id or alias."""
        raise NotImplementedError
