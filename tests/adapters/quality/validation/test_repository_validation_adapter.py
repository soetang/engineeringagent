from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.quality.validation.repository_validation_adapter import (
    QualityRepositoryValidator,
)
from engineeringagent.ports import RepositoryValidationRequest, RepositoryValidationResult


def test_quality_repository_validator_delegates_to_validation_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter forwards the typed request to the validation entrypoint."""
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
        "engineeringagent.adapters.quality.validation.repository_validation_adapter.validate",
        _fake_validate,
    )

    result = QualityRepositoryValidator().validate(
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
