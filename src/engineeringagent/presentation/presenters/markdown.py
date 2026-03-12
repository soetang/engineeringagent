"""Markdown presentation helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.audit import ImplementProgressEnvelope
from engineeringagent.domain.shared import utc_now_iso
from engineeringagent.spec_bundles import progress_kind_label


class HandoffRenderMetadata(BaseModel):
    """Optional rendering metadata for one markdown handoff entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: str | None = None
    used_fallback: bool = False
    progress_kind: str | None = None
    progress_id: str | None = None
    progress_title: str | None = None


def render_handoff_markdown_entry(
    *,
    attempt: int,
    envelope: ImplementProgressEnvelope,
    metadata: HandoffRenderMetadata | None = None,
) -> list[str]:
    """Render deterministic markdown lines for one handoff artifact snapshot."""

    render_metadata = metadata or HandoffRenderMetadata()
    entry_timestamp = render_metadata.timestamp or utc_now_iso()
    lines = [
        f"## Iteration {attempt} - {entry_timestamp}",
        "",
        f"Summary: {envelope.summary}",
    ]
    progress_line = _render_progress_context_line(
        progress_kind=render_metadata.progress_kind,
        progress_id=render_metadata.progress_id,
        progress_title=render_metadata.progress_title,
    )
    if progress_line is not None:
        lines.append(progress_line)
    if render_metadata.used_fallback:
        lines.append("Structured output: invalid_or_missing (deterministic fallback)")

    sections = (
        ("Completed Work", envelope.completed_work),
        ("Verification", envelope.verification),
        ("Blockers", envelope.blockers),
    )
    for title, items in sections:
        lines.extend(_render_markdown_section(title, items))
    return lines


def _render_markdown_section(title: str, items: list[str]) -> list[str]:
    rendered_items = [item for item in items if not _is_placeholder_item(item)]
    if not rendered_items:
        return []
    return ["", f"### {title}", *(f"- {item}" for item in rendered_items), ""]


def _is_placeholder_item(item: str) -> bool:
    return item.strip() == "(none)"


def _render_progress_context_line(
    *,
    progress_kind: str | None,
    progress_id: str | None,
    progress_title: str | None,
) -> str | None:
    reference = _render_progress_reference_label(
        progress_id=progress_id,
        progress_title=progress_title,
    )
    if reference is None:
        return None
    return f"Progress: {progress_kind_label(progress_kind)} {reference}"


def _render_progress_reference_label(
    *,
    progress_id: str | None,
    progress_title: str | None,
) -> str | None:
    normalized_id = (progress_id or "").strip()
    normalized_title = (progress_title or "").strip()
    if normalized_id and normalized_title:
        return f"{normalized_id} - {normalized_title}"
    if normalized_id:
        return normalized_id
    if normalized_title:
        return normalized_title
    return None
