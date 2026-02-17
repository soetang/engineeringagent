from __future__ import annotations

from pathlib import Path

import pytest


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def test_run_checks_fitness_does_not_call_legacy_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engineeringagent.changed_paths import ChangedPathsResult
    from engineeringagent.checks import run_checks

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_all:",
                "    type: fitness",
                "    scope: all",
                "",
            ]
        ),
    )

    def _legacy(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("legacy fitness runtime should not be called")

    # Avoid touching git in tmp_path.
    monkeypatch.setattr(
        "engineeringagent.changed_paths.collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
        raising=True,
    )
    monkeypatch.setattr(
        "engineeringagent.harness_checks_runtime.run_planned_fitness_checks",
        _legacy,
        raising=True,
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["fitness"],
    )
    assert result.ok
    assert "[check:fitness_all] type=fitness scope=all" in result.output
