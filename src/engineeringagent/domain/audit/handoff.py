"""Audit-domain handoff models and parsing helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ImplementProgressEnvelope(BaseModel):
    """Structured implementation handoff payload emitted by implement runs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

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


_FALLBACK_SUMMARY = (
    "Structured handoff output unavailable; recorded deterministic fallback."
)


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
        f"{_progress_kind_label(progress_kind)}{progress_reference}."
    )

    return ImplementProgressEnvelope(
        summary=_FALLBACK_SUMMARY,
        completed_work=[],
        verification=[],
        remaining_work=[remaining_work],
        blockers=[],
    )


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


def _progress_kind_label(progress_kind: str | None) -> str:
    if progress_kind == "phase":
        return "phase"
    return "implementation step"
