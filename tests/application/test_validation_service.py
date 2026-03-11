from __future__ import annotations

from pathlib import Path

from engineeringagent.application import (
    ValidateRepositoryRequest,
    ValidationResult,
    ValidationService,
)
from engineeringagent.ports import (
    RepositoryValidationRequest,
    RepositoryValidationResult,
)


def test_validation_service_returns_ok_when_validator_reports_no_messages() -> None:
    """Service returns a passing result when the validator yields no issues."""
    calls: list[RepositoryValidationRequest] = []

    class _Validator:
        def validate(
            self,
            request: RepositoryValidationRequest,
        ) -> RepositoryValidationResult:
            calls.append(request)
            return RepositoryValidationResult(messages=())

    result = ValidationService(_Validator()).run(
        ValidateRepositoryRequest(
            project_root=Path("/tmp/project"),
            schema_only=True,
        )
    )

    assert result == ValidationResult(ok=True, messages=())
    assert calls == [
        RepositoryValidationRequest(
            project_root=Path("/tmp/project"),
            schema_only=True,
        )
    ]


def test_validation_service_returns_messages_when_validator_fails() -> None:
    """Service preserves validator messages in a stable failing result."""
    class _Validator:
        def validate(
            self,
            request: RepositoryValidationRequest,
        ) -> RepositoryValidationResult:
            assert request.project_root == Path("/tmp/project")
            assert request.schema_only is False
            return RepositoryValidationResult(
                messages=("first issue", "path/to/spec.yaml: second issue")
            )

    result = ValidationService(_Validator()).run(
        ValidateRepositoryRequest(project_root=Path("/tmp/project"))
    )

    assert result == ValidationResult(
        ok=False,
        messages=("first issue", "path/to/spec.yaml: second issue"),
    )
