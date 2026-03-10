"""Structured handoff envelope parsing and markdown rendering helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from engineeringagent.spec_bundles import progress_kind_label

_FALLBACK_SUMMARY = (
    "Structured handoff output unavailable; recorded deterministic fallback."
)


class HandoffRenderMetadata(BaseModel):
    """Optional rendering metadata for one markdown handoff entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: str | None = None
    used_fallback: bool = False
    progress_kind: str | None = None
    progress_id: str | None = None
    progress_title: str | None = None


class ImplementProgressEnvelope(BaseModel):
    """Structured implementation handoff payload emitted by implement runs."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    completed_work: list[str]
    verification: list[str]
    remaining_work: list[str]
    blockers: list[str] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def _summary_must_be_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("summary must be a non-empty string")
        return stripped

    @field_validator(
        "completed_work",
        "verification",
        "remaining_work",
        "blockers",
    )
    @classmethod
    def _list_items_must_be_non_empty_strings(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            stripped = item.strip()
            if not stripped:
                raise ValueError("list fields must contain non-empty strings")
            normalized.append(stripped)
        return normalized


def fallback_implement_progress_envelope(
    *,
    progress_kind: str | None = None,
    progress_id: str | None = None,
    progress_title: str | None = None,
) -> ImplementProgressEnvelope:
    """Return deterministic fallback handoff envelope content."""

    progress_reference = _format_progress_reference(
        progress_id=progress_id,
        progress_title=progress_title,
    )
    remaining_work = (
        "Review latest progress logs and continue the highest-priority open "
        f"{progress_kind_label(progress_kind)}{progress_reference}."
    )

    return ImplementProgressEnvelope(
        summary=_FALLBACK_SUMMARY,
        completed_work=[],
        verification=[],
        remaining_work=[remaining_work],
        blockers=[],
    )


def _format_progress_reference(
    *,
    progress_id: str | None,
    progress_title: str | None,
) -> str:
    normalized_id = (progress_id or "").strip()
    normalized_title = (progress_title or "").strip()
    if normalized_id and normalized_title:
        return f" ({normalized_id}: {normalized_title})"
    if normalized_id:
        return f" ({normalized_id})"
    if normalized_title:
        return f" ({normalized_title})"
    return ""


def parse_implement_progress_envelope(
    payload: object,
    *,
    progress_kind: str | None = None,
    progress_id: str | None = None,
    progress_title: str | None = None,
) -> tuple[ImplementProgressEnvelope, bool]:
    """Parse structured handoff payload; return deterministic fallback when invalid."""

    try:
        envelope = ImplementProgressEnvelope.model_validate(payload)
    except ValidationError:
        return (
            fallback_implement_progress_envelope(
                progress_kind=progress_kind,
                progress_id=progress_id,
                progress_title=progress_title,
            ),
            True,
        )
    return envelope, False


def now_iso() -> str:
    """Return current UTC timestamp in compact ISO-8601 format."""

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def render_handoff_markdown_entry(
    *,
    attempt: int,
    envelope: ImplementProgressEnvelope,
    metadata: HandoffRenderMetadata | None = None,
) -> list[str]:
    """Render deterministic markdown lines for one append-only handoff entry."""

    render_metadata = metadata or HandoffRenderMetadata()
    entry_timestamp = render_metadata.timestamp or now_iso()
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
    """Return True for items that represent synthetic placeholder bullets."""

    return item.strip() == "(none)"


def _render_progress_context_line(
    *,
    progress_kind: str | None,
    progress_id: str | None,
    progress_title: str | None,
) -> str | None:
    """Return a deterministic handoff line naming the active progress unit."""

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
    """Return a compact progress-unit label for markdown handoff entries."""

    normalized_id = (progress_id or "").strip()
    normalized_title = (progress_title or "").strip()
    if normalized_id and normalized_title:
        return f"{normalized_id} - {normalized_title}"
    if normalized_id:
        return normalized_id
    if normalized_title:
        return normalized_title
    return None
