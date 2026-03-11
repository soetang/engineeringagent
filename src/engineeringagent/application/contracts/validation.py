"""Contracts for repository validation."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ValidateRepositoryRequest(BaseModel):
    """Typed input for one repository-validation request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    schema_only: bool = False


class ValidationResult(BaseModel):
    """Stable application result for repository validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    messages: tuple[str, ...]
