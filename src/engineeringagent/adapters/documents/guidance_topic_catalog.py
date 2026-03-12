"""Catalog helpers for packaged guidance topic markdown documents."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
import yaml

from engineeringagent.domain.guidance import UnknownGuidanceTopicIdError
from engineeringagent.domain.shared import TopicId


_APPROACH_TOPIC_ALIASES: dict[str, tuple[str, ...]] = {
    "principles": ("harness-engineering-principles",),
    "specifications": ("spec-writing",),
    "quality-checks": ("quality-check-playbook",),
    "reviewer-authoring": ("reviewer-authoring-guide",),
}
_APPROACH_TOPIC_ORDER = (
    "overview",
    "principles",
    "workflow",
    "specifications",
    "research-session",
    "plan-session",
    "quality-checks",
    "reviewer-authoring",
)
_APPROACH_TOPIC_ORDER_INDEX: dict[str, int] = {
    topic_id: index for index, topic_id in enumerate(_APPROACH_TOPIC_ORDER)
}


class PackagedGuidanceTopic(BaseModel):
    """Metadata for one packaged guidance topic document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_id: TopicId
    aliases: tuple[str, ...]
    title: str
    filename: str
    description: str | None = None

    @property
    def path(self) -> str:
        """Absolute path hint for this topic when rendered from source layout."""
        return str(_source_docs_root() / self.filename)


def _source_docs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "approach" / "docs"


def _packaged_docs_root():
    """Return the package-local guidance docs directory for resource loading."""
    return files("engineeringagent").joinpath("approach").joinpath("docs")


def _guidance_docs_resources() -> list[str]:
    """Return deterministic guidance markdown filenames from packaged resources."""
    docs_root = _packaged_docs_root()
    return [
        resource.name
        for resource in docs_root.iterdir()
        if resource.is_file() and resource.name.endswith(".md")
    ]


def _parse_frontmatter(document: str) -> tuple[dict[str, Any], int]:
    """Parse YAML frontmatter from a guidance markdown document."""
    if not document.startswith("---\n"):
        raise ValueError("approach docs must include YAML frontmatter block")

    frontmatter_end = document.find("\n---", 4)
    if frontmatter_end < 0:
        raise ValueError("approach doc frontmatter is missing closing delimiter")

    frontmatter_block = document[4:frontmatter_end].strip()
    if not frontmatter_block:
        raise ValueError("approach doc frontmatter block is empty")

    parsed = yaml.safe_load(frontmatter_block)
    if not isinstance(parsed, dict):
        raise ValueError("approach doc frontmatter must be a mapping")

    return parsed, frontmatter_end


def _strip_frontmatter(document: str, *, frontmatter_end: int) -> str:
    """Return the markdown body without YAML frontmatter."""
    return document[frontmatter_end + 4 :].lstrip()


def _extract_h1_title(document: str, *, frontmatter_end: int) -> str:
    """Extract the first top-level heading from guidance markdown."""
    body = document[frontmatter_end + 4 :]
    inside_fence = False
    for line in body.splitlines():
        if line.startswith("```"):
            inside_fence = not inside_fence
            continue
        if inside_fence or not line.startswith("# "):
            continue
        return line[2:].strip()

    raise ValueError("approach docs must contain at least one H1 line for title rendering")


def _topic_from_document(*, filename: str, raw_document: str) -> PackagedGuidanceTopic:
    """Load and parse metadata for one packaged guidance markdown document."""
    frontmatter, frontmatter_end = _parse_frontmatter(raw_document)
    approach_id = frontmatter.get("approach_id")
    if not isinstance(approach_id, str) or not approach_id.strip():
        raise ValueError("approach doc frontmatter must define approach_id")
    canonical_id = approach_id.strip()
    description = frontmatter.get("description")
    if description is not None and (
        not isinstance(description, str) or not description.strip()
    ):
        raise ValueError("approach doc frontmatter description must be a non-empty string")

    return PackagedGuidanceTopic(
        canonical_id=canonical_id,
        aliases=tuple(sorted(_APPROACH_TOPIC_ALIASES.get(canonical_id, ()))),
        title=_extract_h1_title(raw_document, frontmatter_end=frontmatter_end),
        filename=filename,
        description=description.strip() if isinstance(description, str) else None,
    )


def _load_packaged_guidance_topic(filename: str) -> PackagedGuidanceTopic:
    """Load and parse metadata for one packaged guidance markdown document."""
    resource = _packaged_docs_root().joinpath(filename)
    return _topic_from_document(
        filename=filename,
        raw_document=resource.read_text(encoding="utf-8"),
    )


@lru_cache(maxsize=1)
def list_packaged_guidance_topics() -> tuple[PackagedGuidanceTopic, ...]:
    """Return deterministic packaged guidance topics."""
    topics: list[PackagedGuidanceTopic] = []
    seen_ids: set[str] = set()
    for filename in _guidance_docs_resources():
        topic = _load_packaged_guidance_topic(filename)
        if topic.canonical_id in seen_ids:
            raise ValueError(f"duplicate approach_id: {topic.canonical_id}")
        seen_ids.add(topic.canonical_id)
        topics.append(topic)

    topics.sort(
        key=lambda topic: _APPROACH_TOPIC_ORDER_INDEX.get(
            topic.canonical_id,
            len(_APPROACH_TOPIC_ORDER),
        )
    )
    return tuple(topics)


def resolve_guidance_topic_id(topic_id: str) -> TopicId:
    """Resolve a canonical id or alias to the canonical topic id."""
    return _resolve_topic(topic_id).canonical_id


def load_guidance_topic_content(topic_id: str) -> str:
    """Return the markdown payload for one guidance topic."""
    topic = _resolve_topic(topic_id)
    return _packaged_docs_root().joinpath(topic.filename).read_text(encoding="utf-8")


def load_guidance_topic_body(topic_id: str) -> str:
    """Return one guidance topic without YAML frontmatter metadata."""
    document = load_guidance_topic_content(topic_id)
    _, frontmatter_end = _parse_frontmatter(document)
    return _strip_frontmatter(document, frontmatter_end=frontmatter_end)


def _resolve_topic(topic_id: str) -> PackagedGuidanceTopic:
    """Resolve a guidance topic id or alias to a matching registry entry."""
    requested = topic_id.strip().lower()
    for topic in list_packaged_guidance_topics():
        if requested == topic.canonical_id or requested in topic.aliases:
            return topic
    raise UnknownGuidanceTopicIdError(f"unknown approach id or alias: {topic_id}")
