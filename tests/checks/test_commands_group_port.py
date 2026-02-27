from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engineeringagent.checks import run_checks
from engineeringagent.process import parse_command_argv


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
        "engineeringagent.process.run_shell_command",
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


def test_parse_command_argv_normalizes_and_splits_tokens() -> None:
    assert parse_command_argv('  python -c "print(1)"  ') == (
        "python",
        "-c",
        "print(1)",
    )


def test_parse_command_argv_rejects_blank_command() -> None:
    with pytest.raises(ValueError, match="non-empty argv-style string"):
        parse_command_argv("   ")


def test_parse_command_argv_rejects_shell_operators() -> None:
    with pytest.raises(ValueError, match="shell syntax is not supported"):
        parse_command_argv("echo hi | cat")


def test_parse_command_argv_rejects_embedded_backticks() -> None:
    with pytest.raises(ValueError, match="shell syntax is not supported"):
        parse_command_argv("echo `uname`")


@pytest.mark.parametrize("command", ["echo $HOME", "echo ${HOME}"])
def test_parse_command_argv_rejects_embedded_variable_expansion(command: str) -> None:
    with pytest.raises(ValueError, match="shell syntax is not supported"):
        parse_command_argv(command)
