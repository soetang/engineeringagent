from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.shell import (
    SubprocessShellRunner,
    parse_command_argv,
    run_shell_command,
)


def test_run_shell_command_uses_subprocess_shell_runner(tmp_path: Path) -> None:
    """Exercise the default adapter entrypoint through a real subprocess."""
    result = run_shell_command(tmp_path, 'python -c "print(1)"')

    assert result.returncode == 0
    assert result.stdout.strip() == "1"
    assert result.stderr == ""


def test_subprocess_shell_runner_rejects_shell_operators(tmp_path: Path) -> None:
    """Reject shell-only syntax before launching a subprocess."""
    result = SubprocessShellRunner().run(tmp_path, "echo hi | cat")

    assert result.returncode == 2
    assert "shell syntax is not supported" in result.stderr


def test_subprocess_shell_runner_reports_missing_executable(tmp_path: Path) -> None:
    """Return a stable failure record when the executable is unavailable."""
    result = SubprocessShellRunner().run(tmp_path, "definitely-not-an-installed-command")

    assert result.returncode == 127
    assert "command executable not found" in result.stderr


def test_parse_command_argv_normalizes_and_splits_tokens() -> None:
    """Trim leading/trailing whitespace while preserving argv tokens."""
    assert parse_command_argv('  python -c "print(1)"  ') == (
        "python",
        "-c",
        "print(1)",
    )


def test_parse_command_argv_rejects_blank_command() -> None:
    """Reject empty command strings early."""
    with pytest.raises(ValueError, match="non-empty argv-style string"):
        parse_command_argv("   ")


@pytest.mark.parametrize(
    "command",
    [
        "echo hi | cat",
        "echo hi && echo again",
        "echo hi; echo again",
        "echo hi || echo again",
        "echo hi > /tmp/engineeragent-checks.out",
        "cat < /tmp/engineeragent-checks.in",
        "echo hi |& cat",
    ],
)
def test_parse_command_argv_rejects_shell_operators(command: str) -> None:
    """Disallow shell control operators in argv-style command strings."""
    with pytest.raises(ValueError, match="shell syntax is not supported"):
        parse_command_argv(command)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("echo $HOME", ("echo", "$HOME")),
        ("echo ${HOME}", ("echo", "${HOME}")),
        ("echo `uname`", ("echo", "`uname`")),
    ],
)
def test_parse_command_argv_allows_embedded_shell_like_text(
    command: str,
    expected: tuple[str, ...],
) -> None:
    """Preserve shell-like text when it appears inside plain arguments."""
    assert parse_command_argv(command) == expected
