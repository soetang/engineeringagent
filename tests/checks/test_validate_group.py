from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.application.checks.runtime import run_checks


def test_run_checks_validate_group_delegates_to_checks_validate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def _fake_validate(project_root: Path, *, schema_only: bool = False) -> list[str]:
        assert schema_only is False
        calls.append(project_root)
        return ["validate: boom"]

    monkeypatch.setattr(
        "engineeringagent.checks.strategies.validate",
        _fake_validate,
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["validate"])

    assert calls == [tmp_path.resolve()]
    assert not result.ok
    assert result.failed_check_id == "validate"
    assert "validate: boom" in result.output


def test_run_checks_validate_group_passes_schema_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def _fake_validate(_project_root: Path, *, schema_only: bool = False) -> list[str]:
        calls.append(schema_only)
        return []

    monkeypatch.setattr(
        "engineeringagent.checks.strategies.validate",
        _fake_validate,
    )

    result = run_checks(
        tmp_path,
        phase="manual",
        checks=["validate"],
        schema_only=True,
    )

    assert result.ok
    assert calls == [True]
