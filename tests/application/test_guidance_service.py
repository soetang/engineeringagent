from __future__ import annotations

import re

import pytest

from engineeringagent.application import (
    DefaultGuidanceService,
    GuidanceInputError,
    GuidanceQuery,
)
from tests.cli.approach_fixture_data import APPROACH_TOPIC_IDS

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


def test_default_guidance_service_renders_overview_with_topic_index() -> None:
    """Overview rendering includes the stable topic index section."""
    result = DefaultGuidanceService().render(GuidanceQuery(kind="overview"))

    assert result.output_prefix == "approach overview written"
    assert "Available approach topics:" in result.payload
    index_payload = result.payload.split("Available approach topics:\n", 1)[1]
    assert _parse_approach_topic_ids(index_payload) == APPROACH_TOPIC_IDS


def test_default_guidance_service_renders_topic_list() -> None:
    """List rendering preserves stable topic order and output metadata."""
    result = DefaultGuidanceService().render(GuidanceQuery(kind="list"))

    assert result.output_prefix == "approach list written"
    assert _parse_approach_topic_ids(result.payload) == APPROACH_TOPIC_IDS


def test_default_guidance_service_renders_topic_body_without_frontmatter() -> None:
    """Topic rendering strips frontmatter before returning the markdown body."""
    result = DefaultGuidanceService().render(
        GuidanceQuery(kind="topic", topic_id="specifications")
    )

    assert result.output_prefix == "approach topic written"
    assert result.payload.startswith("# Spec Writing Guide")
    assert not result.payload.startswith("---\n")


def test_default_guidance_service_rejects_blank_topic_requests() -> None:
    """Blank topic ids are rejected before adapter lookup runs."""
    with pytest.raises(GuidanceInputError):
        DefaultGuidanceService().render(GuidanceQuery(kind="topic", topic_id="  "))
