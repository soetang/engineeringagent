from __future__ import annotations

from pathlib import Path

from engineeringagent.application import (
    DefaultValidationService,
    ValidateRepositoryRequest,
    ValidationResult,
)


def test_validation_service_returns_ok_when_validator_reports_no_messages() -> None:
    """Service returns a passing result when the validator yields no issues."""
    calls: list[tuple[Path, bool]] = []

    class _Validator:
        def validate(
            self,
            project_root: Path,
            *,
            schema_only: bool = False,
        ) -> list[str]:
            calls.append((project_root, schema_only))
            return []

    result = DefaultValidationService(_Validator()).run(
        ValidateRepositoryRequest(
            project_root=Path("/tmp/project"),
            schema_only=True,
        )
    )

    assert result == ValidationResult(ok=True, messages=())
    assert calls == [(Path("/tmp/project"), True)]


def test_validation_service_returns_messages_when_validator_fails() -> None:
    """Service preserves validator messages in a stable failing result."""
    class _Validator:
        def validate(
            self,
            project_root: Path,
            *,
            schema_only: bool = False,
        ) -> list[str]:
            assert project_root == Path("/tmp/project")
            assert schema_only is False
            return ["first issue", "path/to/spec.yaml: second issue"]

    result = DefaultValidationService(_Validator()).run(
        ValidateRepositoryRequest(project_root=Path("/tmp/project"))
    )

    assert result == ValidationResult(
        ok=False,
        messages=("first issue", "path/to/spec.yaml: second issue"),
    )
