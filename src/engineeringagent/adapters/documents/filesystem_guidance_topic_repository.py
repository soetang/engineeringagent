"""Filesystem-oriented guidance topic repository adapter."""

from __future__ import annotations

from engineeringagent.domain.guidance import GuidanceTopic
from engineeringagent.ports import GuidanceTopicRepository

from .guidance_topic_catalog import (
    list_packaged_guidance_topics,
    load_guidance_topic_body,
    load_guidance_topic_content,
    resolve_guidance_topic_id,
)


class FilesystemGuidanceTopicRepository(GuidanceTopicRepository):
    """Guidance repository backed by local approach documents."""

    def list_topics(self) -> tuple[GuidanceTopic, ...]:
        """Return local guidance topics in deterministic order."""
        return tuple(
            GuidanceTopic(
                canonical_id=topic.canonical_id,
                aliases=topic.aliases,
                title=topic.title,
                description=topic.description,
                document=None,
                body=None,
            )
            for topic in list_packaged_guidance_topics()
        )

    def load(self, topic_id: str) -> GuidanceTopic:
        """Load one topic body by canonical id or alias."""
        canonical_id = resolve_guidance_topic_id(topic_id)
        topic = next(
            item for item in self.list_topics() if item.canonical_id == canonical_id
        )
        return GuidanceTopic(
            canonical_id=topic.canonical_id,
            aliases=topic.aliases,
            title=topic.title,
            description=topic.description,
            document=load_guidance_topic_content(canonical_id),
            body=load_guidance_topic_body(canonical_id),
        )
