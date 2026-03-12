"""Contracts for approach guidance rendering."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GuidanceQuery(BaseModel):
    """Typed input for one guidance request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str
    topic_id: str | None = None


class GuidanceResult(BaseModel):
    """Stable application result for guidance rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    payload: str
    output_prefix: str
