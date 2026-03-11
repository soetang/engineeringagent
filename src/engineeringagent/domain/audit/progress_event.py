"""Audit-domain progress event model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProgressEvent(BaseModel):
    """One append-only operational event emitted by runtime flows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: str
    event_kind: str
    feature_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_log_record(self) -> dict[str, Any]:
        """Render the event as one flat JSONL record for append-only sinks."""

        record = dict(self.payload)
        record["timestamp"] = self.timestamp
        record["event_kind"] = self.event_kind
        if self.feature_id is not None:
            record["feature_id"] = self.feature_id
        return record
