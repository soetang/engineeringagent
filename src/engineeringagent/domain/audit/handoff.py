"""Audit-domain handoff models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
