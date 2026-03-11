"""Checks-backed repository validation adapter."""

from __future__ import annotations

from engineeringagent.checks import validate_repository
from engineeringagent.ports import (
    RepositoryValidationRequest,
    RepositoryValidationResult,
)


class ChecksRepositoryValidator:
    """Adapter that delegates repository validation to the checks package."""

    def validate(
        self,
        request: RepositoryValidationRequest,
    ) -> RepositoryValidationResult:
        """Return repository validation messages."""
        return RepositoryValidationResult(
            messages=tuple(
                validate_repository(
                    request.project_root,
                    schema_only=request.schema_only,
                )
            )
        )
