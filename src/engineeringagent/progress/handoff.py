"""Structured handoff envelope parsing and markdown rendering helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from . import logging as progress_logging

_FALLBACK_SUMMARY = (
    "Structured handoff output unavailable; recorded deterministic fallback."
)
_FALLBACK_REMAINING_WORK = (
    "Review latest progress logs and continue the highest-priority open subtask."
)


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


def fallback_implement_progress_envelope() -> ImplementProgressEnvelope:
    """Return deterministic fallback handoff envelope content."""

    return ImplementProgressEnvelope(
        summary=_FALLBACK_SUMMARY,
        completed_work=[],
        verification=[],
        remaining_work=[_FALLBACK_REMAINING_WORK],
        blockers=[],
    )


def parse_implement_progress_envelope(
    payload: object,
) -> tuple[ImplementProgressEnvelope, bool]:
    """Parse structured handoff payload; return deterministic fallback when invalid."""

    try:
        envelope = ImplementProgressEnvelope.model_validate(payload)
    except ValidationError:
        return fallback_implement_progress_envelope(), True
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
    timestamp: str | None = None,
    used_fallback: bool = False,
) -> list[str]:
    """Render deterministic markdown lines for one append-only handoff entry."""

    entry_timestamp = timestamp or now_iso()
    lines = [
        f"## Iteration {attempt} - {entry_timestamp}",
        "",
        f"Summary: {envelope.summary}",
    ]
    if used_fallback:
        lines.append("Structured output: invalid_or_missing (deterministic fallback)")

    sections = (
        ("Completed Work", envelope.completed_work),
        ("Verification", envelope.verification),
        ("Remaining Work", envelope.remaining_work),
        ("Blockers", envelope.blockers),
    )
    for title, items in sections:
        lines.extend(_render_markdown_section(title, items))
    return lines


def append_handoff_markdown_entry(
    *, handoff_path: Path, entry_lines: list[str]
) -> None:
    """Append one rendered markdown handoff entry to the feature handoff file."""

    progress_logging.append_text_block(log_path=handoff_path, lines=entry_lines)


def _render_markdown_list(items: list[str]) -> list[str]:
    if not items:
        return ["- (none)"]
    return [f"- {item}" for item in items]


def _render_markdown_section(title: str, items: list[str]) -> list[str]:
    return ["", f"### {title}", *_render_markdown_list(items), ""]
