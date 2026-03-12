from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.quality.repository_validator import (
    ChecksRepositoryValidator,
)
from engineeringagent.ports import RepositoryValidationRequest, RepositoryValidationResult


def test_checks_repository_validator_delegates_to_checks_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter forwards the typed request to the concrete validator entrypoint."""
    captured: dict[str, object] = {}

    def _fake_validate(
        project_root: Path,
        *,
        schema_only: bool = False,
    ) -> list[str]:
        captured["project_root"] = project_root
        captured["schema_only"] = schema_only
        return ["issue one", "issue two"]

    monkeypatch.setattr(
        "engineeringagent.adapters.quality.repository_validator.validate",
        _fake_validate,
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
