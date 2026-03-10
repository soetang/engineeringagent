"""Application service for repository validation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from engineeringagent.checks import validate_repository


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


class RepositoryValidator(Protocol):
    """Validation callable used by the application service."""

    def __call__(
        self,
        project_root: Path,
        *,
        schema_only: bool = False,
    ) -> list[str]: ...


class ValidationService:
    """Owns static repository validation."""

    def run(self, request: ValidateRepositoryRequest) -> ValidationResult:
        """Run one repository validation request."""
        raise NotImplementedError


class DefaultValidationService(ValidationService):
    """Application validation service backed by the repository validator."""

    def __init__(
        self,
        validator: RepositoryValidator = validate_repository,
    ) -> None:
        self._validator = validator

    def run(self, request: ValidateRepositoryRequest) -> ValidationResult:
        """Run one repository validation request."""
        messages = tuple(
            self._validator(
                request.project_root,
                schema_only=request.schema_only,
            )
        )
        return ValidationResult(
            ok=not messages,
            messages=messages,
        )
