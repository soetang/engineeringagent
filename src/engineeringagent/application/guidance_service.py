"""Application service for approach guidance rendering."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.guidance import GuidanceTopic
from engineeringagent.ports import GuidanceTopicRepository


class GuidanceQuery(BaseModel):
    """Typed input for one guidance rendering request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["overview", "list", "topic"]
    topic_id: str | None = None


class GuidanceResult(BaseModel):
    """Rendered guidance payload plus stable output metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    payload: str
    output_prefix: str


class GuidanceInputError(ValueError):
    """Raised when a guidance request is missing required input."""


class GuidanceService:
    """Owns approach topic discovery and rendering."""

    def __init__(self, topic_repository: GuidanceTopicRepository) -> None:
        self._topic_repository = topic_repository

    def render(self, query: GuidanceQuery) -> GuidanceResult:
        """Render one guidance response for the requested query kind."""
        if query.kind == "overview":
            overview = self._require_document(self._topic_repository.load("overview"))
            return GuidanceResult(
                payload=_render_overview(overview, self._topic_repository.list_topics()),
                output_prefix="approach overview written",
            )

        if query.kind == "list":
            rendered = (
                _format_topic_index(self._topic_repository.list_topics())
                or "No approach topics are available."
            )
            return GuidanceResult(
                payload=rendered,
                output_prefix="approach list written",
            )

        topic_id = (query.topic_id or "").strip()
        if topic_id == "":
            raise GuidanceInputError(
                "provide a topic id or use `engineeringagent approach list`"
            )
        topic = self._topic_repository.load(topic_id)
        return GuidanceResult(
            payload=self._require_body(topic),
            output_prefix="approach topic written",
        )

    def _require_body(self, topic: GuidanceTopic) -> str:
        if topic.body is None:
            raise ValueError(
                f"guidance topic body is missing for {topic.canonical_id}"
            )
        return topic.body

    def _require_document(self, topic: GuidanceTopic) -> str:
        if topic.document is None:
            raise ValueError(
                f"guidance topic document is missing for {topic.canonical_id}"
            )
        return topic.document


def _format_topic_index(topics: tuple[GuidanceTopic, ...]) -> str:
    """Render a deterministic stable-order topic index as markdown payload lines."""

    return "\n".join(
        (
            f"{topic.canonical_id}: {topic.title} - {topic.description}"
            if topic.description
            else f"{topic.canonical_id}: {topic.title}"
        )
        for topic in topics
    )


def _render_overview(overview_payload: str, topics: tuple[GuidanceTopic, ...]) -> str:
    """Render guidance overview with a deterministic topic index section."""

    return (
        f"{overview_payload.rstrip()}\n\nAvailable approach topics:\n"
        f"{_format_topic_index(topics)}"
    )
