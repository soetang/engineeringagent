"""Packaged approach documentation registry."""

from __future__ import annotations
from functools import lru_cache

from importlib.resources import files
from typing import Any

from pydantic import BaseModel, ConfigDict
import yaml

_SCHEME = "engineeringagent.approach"
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


class ApproachTopic(BaseModel):
    """Metadata for one packaged approach topic document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_id: str
    aliases: tuple[str, ...]
    title: str
    filename: str
    description: str | None = None

    @property
    def path(self) -> str:
        """Absolute path hint for this approach topic when rendered in source tree."""
        return str(_approach_docs_root() / self.filename)


def _approach_docs_root():
    """Return the package-local approach docs directory for resource loading."""
    return files(_SCHEME).joinpath("docs")


class UnknownApproachIdError(ValueError):
    """Raised when a topic id or alias cannot be resolved."""


def _approach_docs_resources() -> list[str]:
    """Return deterministic approach markdown filenames from package resources."""
    docs_root = _approach_docs_root()
    return [
        resource.name
        for resource in docs_root.iterdir()
        if resource.is_file() and resource.name.endswith(".md")
    ]


def _parse_frontmatter(document: str) -> tuple[dict[str, Any], int]:
    """Parse YAML frontmatter from an approach markdown document."""
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
    """Extract the first top-level heading from approach markdown payload."""
    body = document[frontmatter_end + 4 :]
    inside_fence = False
    for line in body.splitlines():
        if line.startswith("```"):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        if not line.startswith("# "):
            continue
        return line[2:].strip()

    raise ValueError("approach docs must contain at least one H1 line for title rendering")


def _topic_from_document(
    *,
    filename: str,
    raw_document: str,
) -> ApproachTopic:
    """Load and parse metadata for one approach markdown document."""
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
    title = _extract_h1_title(raw_document, frontmatter_end=frontmatter_end)
    aliases = _APPROACH_TOPIC_ALIASES.get(canonical_id, ())

    return ApproachTopic(
        canonical_id=canonical_id,
        aliases=tuple(sorted(aliases)),
        title=title,
        filename=filename,
        description=description.strip() if isinstance(description, str) else None,
    )


def _load_packaged_approach_topic(filename: str) -> ApproachTopic:
    """Load and parse metadata for one packaged approach markdown document."""
    resource = _approach_docs_root().joinpath(filename)
    return _topic_from_document(
        filename=filename,
        raw_document=resource.read_text(encoding="utf-8"),
    )


@lru_cache(maxsize=1)
def list_approach_topics() -> tuple[ApproachTopic, ...]:
    """Return deterministic packaged approach topics."""
    topics: list[ApproachTopic] = []
    seen_ids: set[str] = set()
    for filename in _approach_docs_resources():
        topic = _load_packaged_approach_topic(filename)
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


def resolve_approach_topic_id(topic_id: str) -> str:
    """Resolve a canonical id or alias to canonical topic id."""
    return _resolve_topic(topic_id).canonical_id


def load_topic_content(topic_id: str) -> str:
    """Return the markdown payload for one approach topic."""
    topic = _resolve_topic(topic_id)
    return _approach_docs_root().joinpath(topic.filename).read_text(encoding="utf-8")


def load_topic_body(topic_id: str) -> str:
    """Return one approach topic without YAML frontmatter metadata."""
    document = load_topic_content(topic_id)
    _, frontmatter_end = _parse_frontmatter(document)
    return _strip_frontmatter(document, frontmatter_end=frontmatter_end)


def _resolve_topic(topic_id: str) -> ApproachTopic:
    """Resolve an approach topic id or alias to a matching registry entry."""
    requested = topic_id.strip().lower()
    for topic in list_approach_topics():
        if requested == topic.canonical_id or requested in topic.aliases:
            return topic

    raise UnknownApproachIdError(f"unknown approach id or alias: {topic_id}")
