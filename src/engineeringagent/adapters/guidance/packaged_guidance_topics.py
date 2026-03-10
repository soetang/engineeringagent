"""Packaged guidance topic repository adapter."""

from __future__ import annotations

from engineeringagent.approach import (
    list_approach_topics,
    load_topic_content,
    load_topic_body,
    resolve_approach_topic_id,
)
from engineeringagent.ports import GuidanceTopic, GuidanceTopicRepository


class PackagedGuidanceTopicRepository(GuidanceTopicRepository):
    """Guidance repository backed by packaged approach documents."""

    def list_topics(self) -> tuple[GuidanceTopic, ...]:
        """Return packaged approach topics in deterministic order."""
        return tuple(
            GuidanceTopic(
                canonical_id=topic.canonical_id,
                aliases=topic.aliases,
                title=topic.title,
                description=topic.description,
                document=None,
                body=None,
            )
            for topic in list_approach_topics()
        )

    def load(self, topic_id: str) -> GuidanceTopic:
        """Load one topic body by canonical id or alias."""
        canonical_id = resolve_approach_topic_id(topic_id)
        topic = next(
            item for item in self.list_topics() if item.canonical_id == canonical_id
        )
        return GuidanceTopic(
            canonical_id=topic.canonical_id,
            aliases=topic.aliases,
            title=topic.title,
            description=topic.description,
            document=load_topic_content(canonical_id),
            body=load_topic_body(canonical_id),
        )
