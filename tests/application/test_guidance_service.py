from __future__ import annotations

import re

import pytest

from engineeringagent.application import (
    GuidanceInputError,
    GuidanceQuery,
    GuidanceService,
)
from engineeringagent.domain.guidance import GuidanceTopic
from tests.presentation.cli.approach_fixture_data import APPROACH_TOPIC_IDS

_APPROACH_TOPIC_ID_PREFIX = re.compile(r"^\s*(?P<topic_id>[A-Za-z0-9-]+):")


def _parse_approach_topic_ids(payload: str) -> tuple[str, ...]:
    """Extract rendered topic ids from a markdown list payload."""
    topic_ids: list[str] = []
    for line in payload.splitlines():
        match = _APPROACH_TOPIC_ID_PREFIX.match(line)
        if match is None:
            continue
        topic_ids.append(match.group("topic_id"))
    return tuple(topic_ids)


class _FakeGuidanceRepository:
    def __init__(self, topics: tuple[GuidanceTopic, ...]) -> None:
        self._topics = topics

    def list_topics(self) -> tuple[GuidanceTopic, ...]:
        return self._topics

    def load(self, topic_id: str) -> GuidanceTopic:
        requested = topic_id.strip().lower()
        for topic in self._topics:
            if requested == topic.canonical_id or requested in topic.aliases:
                return topic
        raise ValueError(f"unknown topic: {topic_id}")


def test_default_guidance_service_renders_overview_with_topic_index() -> None:
    """Overview rendering includes the stable topic index section."""
    repo = _FakeGuidanceRepository(
        (
            GuidanceTopic(
                canonical_id="overview",
                aliases=(),
                title="Overview",
                description=None,
                document="---\napproach_id: overview\n---\n# Overview\n",
                body="# Overview\n",
            ),
            GuidanceTopic(
                canonical_id="specifications",
                aliases=("spec-writing",),
                title="Spec Writing Guide",
                description="How to write specs",
                document=None,
                body="# Spec Writing Guide\n",
            ),
        )
    )
    result = GuidanceService(repo).render(GuidanceQuery(kind="overview"))

    assert result.output_prefix == "approach overview written"
    assert "Available approach topics:" in result.payload
    index_payload = result.payload.split("Available approach topics:\n", 1)[1]
    assert _parse_approach_topic_ids(index_payload) == ("overview", "specifications")


def test_default_guidance_service_renders_topic_list() -> None:
    """List rendering preserves stable topic order and output metadata."""
    repo = _FakeGuidanceRepository(
        tuple(
            GuidanceTopic(
                canonical_id=topic_id,
                aliases=(),
                title=topic_id.title(),
                description=None,
                document=f"---\napproach_id: {topic_id}\n---\n# {topic_id.title()}\n",
                body=f"# {topic_id.title()}\n",
            )
            for topic_id in APPROACH_TOPIC_IDS
        )
    )
    result = GuidanceService(repo).render(GuidanceQuery(kind="list"))

    assert result.output_prefix == "approach list written"
    assert _parse_approach_topic_ids(result.payload) == APPROACH_TOPIC_IDS


def test_default_guidance_service_renders_topic_body_without_frontmatter() -> None:
    """Topic rendering strips frontmatter before returning the markdown body."""
    repo = _FakeGuidanceRepository(
        (
            GuidanceTopic(
                canonical_id="specifications",
                aliases=("spec-writing",),
                title="Spec Writing Guide",
                description=None,
                document=None,
                body="# Spec Writing Guide\n",
            ),
        )
    )
    result = GuidanceService(repo).render(
        GuidanceQuery(kind="topic", topic_id="spec-writing")
    )

    assert result.output_prefix == "approach topic written"
    assert result.payload.startswith("# Spec Writing Guide")


def test_default_guidance_service_rejects_missing_topic_body() -> None:
    """Rendered guidance requires the repository to provide a topic body."""
    repo = _FakeGuidanceRepository(
        (
            GuidanceTopic(
                canonical_id="specifications",
                aliases=("spec-writing",),
                title="Spec Writing Guide",
                description=None,
                document=None,
                body=None,
            ),
        )
    )

    with pytest.raises(ValueError, match="guidance topic body is missing"):
        GuidanceService(repo).render(
            GuidanceQuery(kind="topic", topic_id="spec-writing")
        )


def test_default_guidance_service_rejects_missing_overview_document() -> None:
    """Overview rendering requires the repository to provide raw document content."""
    repo = _FakeGuidanceRepository(
        (
            GuidanceTopic(
                canonical_id="overview",
                aliases=(),
                title="Overview",
                description=None,
                document=None,
                body="# Overview\n",
            ),
        )
    )

    with pytest.raises(ValueError, match="guidance topic document is missing"):
        GuidanceService(repo).render(GuidanceQuery(kind="overview"))


def test_default_guidance_service_rejects_blank_topic_requests() -> None:
    """Blank topic ids are rejected before adapter lookup runs."""
    with pytest.raises(GuidanceInputError):
        GuidanceService(_FakeGuidanceRepository(())).render(
            GuidanceQuery(kind="topic", topic_id="  ")
        )


def test_guidance_topic_rejects_blank_canonical_id() -> None:
    """Guidance topics should validate canonical ids through the shared kernel."""
    with pytest.raises(ValueError, match="String should have at least 1 character"):
        GuidanceTopic(
            canonical_id="",
            aliases=(),
            title="Overview",
            description=None,
            document="# Overview\n",
            body="# Overview\n",
        )
