from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.checks import ChecksRepositoryValidator
from engineeringagent.ports import RepositoryValidationRequest, RepositoryValidationResult


def test_checks_repository_validator_delegates_to_checks_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter forwards the typed request to the checks validation surface."""
    captured: dict[str, object] = {}

    def _fake_validate_repository(
        project_root: Path,
        *,
        schema_only: bool = False,
    ) -> list[str]:
        captured["project_root"] = project_root
        captured["schema_only"] = schema_only
        return ["issue one", "issue two"]

    monkeypatch.setattr(
        "engineeringagent.adapters.checks.repository_validator.validate_repository",
        _fake_validate_repository,
    )

    result = ChecksRepositoryValidator().validate(
        RepositoryValidationRequest(
            project_root=Path("/tmp/project"),
            schema_only=True,
        )
    )

    assert result == RepositoryValidationResult(
        messages=("issue one", "issue two"),
    )
    assert captured == {
        "project_root": Path("/tmp/project"),
        "schema_only": True,
    }
