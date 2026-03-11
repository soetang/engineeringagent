"""Application service for repository validation."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.ports import RepositoryValidator


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


class ValidationService:
    """Owns static repository validation."""

    def __init__(self, validator: RepositoryValidator) -> None:
        self._validator = validator

    def run(self, request: ValidateRepositoryRequest) -> ValidationResult:
        """Run one repository validation request."""
        messages = tuple(
            self._validator.validate(
                request.project_root,
                schema_only=request.schema_only,
            )
        )
        return ValidationResult(
            ok=not messages,
            messages=messages,
        )
