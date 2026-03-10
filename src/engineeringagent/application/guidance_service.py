"""Application service for approach guidance rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from engineeringagent.approach import (
    format_approach_topic_index,
    load_topic_body,
    load_topic_content,
    render_approach_overview,
)


@dataclass(frozen=True)
class GuidanceQuery:
    """Typed input for one guidance rendering request."""

    kind: Literal["overview", "list", "topic"]
    topic_id: str | None = None


@dataclass(frozen=True)
class GuidanceResult:
    """Rendered guidance payload plus stable output metadata."""

    payload: str
    output_prefix: str


class GuidanceInputError(ValueError):
    """Raised when a guidance request is missing required input."""


class GuidanceService:
    """Owns approach topic discovery and rendering."""

    def render(self, query: GuidanceQuery) -> GuidanceResult:
        """Render one guidance response for the requested query kind."""
        raise NotImplementedError


class DefaultGuidanceService(GuidanceService):
    """Application guidance service backed by packaged approach docs."""

    def __init__(
        self,
        *,
        load_topic_content_fn: Callable[[str], str] = load_topic_content,
        load_topic_body_fn: Callable[[str], str] = load_topic_body,
        format_topic_index_fn: Callable[[], str] = format_approach_topic_index,
        render_overview_fn: Callable[[str], str] = render_approach_overview,
    ) -> None:
        self._load_topic_content = load_topic_content_fn
        self._load_topic_body = load_topic_body_fn
        self._format_topic_index = format_topic_index_fn
        self._render_overview = render_overview_fn

    def render(self, query: GuidanceQuery) -> GuidanceResult:
        """Render one guidance response for the requested query kind."""
        if query.kind == "overview":
            overview = self._load_topic_content("overview")
            return GuidanceResult(
                payload=self._render_overview(overview),
                output_prefix="approach overview written",
            )

        if query.kind == "list":
            rendered = self._format_topic_index() or "No approach topics are available."
            return GuidanceResult(
                payload=rendered,
                output_prefix="approach list written",
            )

        topic_id = (query.topic_id or "").strip()
        if topic_id == "":
            raise GuidanceInputError(
                "provide a topic id or use `engineeringagent approach list`"
            )
        return GuidanceResult(
            payload=self._load_topic_body(topic_id),
            output_prefix="approach topic written",
        )
