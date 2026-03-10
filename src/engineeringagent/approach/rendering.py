"""Rendering helpers for approach command output."""

from __future__ import annotations

from .registry import ApproachTopic, list_approach_topics


def format_approach_topic_index(topics: tuple[ApproachTopic, ...] | None = None) -> str:
    """Render a deterministic stable-order topic index as markdown payload lines."""

    if topics is None:
        topics = list_approach_topics()
    return "\n".join(
        (
            f"{topic.canonical_id}: {topic.title} - {topic.description}"
            if topic.description
            else f"{topic.canonical_id}: {topic.title}"
        )
        for topic in topics
    )


def render_approach_overview(overview_payload: str) -> str:
    """Render approach overview with a deterministic topic index section."""

    return (
        f"{overview_payload.rstrip()}\n\nAvailable approach topics:\n"
        f"{format_approach_topic_index()}"
    )
