"""Contracts for guidance rendering."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class GuidanceQuery(BaseModel):
    """Typed input for one guidance rendering request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["overview", "list", "topic"]
    topic_id: str | None = None


class GuidanceResult(BaseModel):
    """Rendered guidance payload plus stable output metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    payload: str
    output_prefix: str


class GuidanceInputError(ValueError):
    """Raised when a guidance request is missing required input."""
