"""Application service for repository validation."""

from __future__ import annotations

from engineeringagent.application.contracts.validation import (
    ValidateRepositoryRequest,
    ValidationResult,
)
from engineeringagent.ports import (
    RepositoryValidationRequest,
    RepositoryValidator,
)


class ValidationService:
    """Owns static repository validation."""

    def __init__(self, validator: RepositoryValidator) -> None:
        self._validator = validator

    def run(self, request: ValidateRepositoryRequest) -> ValidationResult:
        """Run one repository validation request."""
        port_result = self._validator.validate(
            RepositoryValidationRequest(
                project_root=request.project_root,
                schema_only=request.schema_only,
            )
        )
        return ValidationResult(
            ok=not port_result.messages,
            messages=port_result.messages,
        )
