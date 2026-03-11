"""Repository validation port used by the application layer."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class RepositoryValidationRequest(BaseModel):
    """Stable request envelope for one repository validation run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    schema_only: bool = False


class RepositoryValidationResult(BaseModel):
    """Stable result envelope for one repository validation run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    messages: tuple[str, ...]


class RepositoryValidator(Protocol):
    """Run repository validation without exposing checks implementation details."""

    def validate(
        self,
        request: RepositoryValidationRequest,
    ) -> RepositoryValidationResult:
        """Return validation messages for one repository request."""
        raise NotImplementedError
