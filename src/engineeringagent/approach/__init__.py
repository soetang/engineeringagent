"""Approach guidance package."""

from .registry import (
    ApproachTopic,
    UnknownApproachIdError,
    list_approach_topics,
    load_topic_content,
    resolve_approach_topic_id,
)
from .rendering import (
    format_approach_topic_index,
    render_approach_overview,
)

__all__ = [
    "ApproachTopic",
    "UnknownApproachIdError",
    "list_approach_topics",
    "load_topic_content",
    "resolve_approach_topic_id",
    "format_approach_topic_index",
    "render_approach_overview",
]
