from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engineeringagent.checks import run_checks


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def test_run_checks_commands_does_not_call_legacy_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "",
            ]
        ),
    )

    def _run_shell_command(_root: Path, _command: str) -> object:
        return SimpleNamespace(returncode=0, stdout="hi\n", stderr="")

    monkeypatch.setattr(
        "engineeringagent.opencode.client.run_shell_command",
        _run_shell_command,
        raising=True,
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["commands"],
    )
    assert result.ok
    assert "[check:smoke] command=echo hi" in result.output
    assert "[check:smoke] returncode=0" in result.output
    assert "hi" in result.output
