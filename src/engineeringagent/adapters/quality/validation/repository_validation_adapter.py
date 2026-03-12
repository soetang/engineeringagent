"""Repository-validation adapter backed by the quality validation package."""

from __future__ import annotations

from engineeringagent.adapters.quality.validation.validator import validate
from engineeringagent.ports import (
    RepositoryValidationRequest,
    RepositoryValidationResult,
)


class QualityRepositoryValidator:
    """Adapt the validation port to the quality validation entrypoint."""

    def validate(
        self,
        request: RepositoryValidationRequest,
    ) -> RepositoryValidationResult:
        """Return repository validation messages for one request."""
        return RepositoryValidationResult(
            messages=tuple(
                validate(
                    request.project_root,
                    schema_only=request.schema_only,
                )
            )
        )
