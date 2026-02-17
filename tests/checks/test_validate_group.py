from __future__ import annotations

from pathlib import Path

import pytest


def test_run_checks_validate_group_delegates_to_checks_validate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engineeringagent.checks.api import run_checks

    calls: list[Path] = []

    def _fake_validate(project_root: Path, *, schema_only: bool = False) -> list[str]:
        assert schema_only is False
        calls.append(project_root)
        return ["validate: boom"]

    monkeypatch.setattr(
        "engineeringagent.checks.validate.runtime.run_validate",
        _fake_validate,
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["validate"])

    assert calls == [tmp_path.resolve()]
    assert not result.ok
    assert result.failed_group == "validate"
    assert "validate: boom" in result.output
