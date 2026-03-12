from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from engineeringagent.checks import run_checks
from engineeringagent.domain.quality import HarnessCheckPhase

from tests.checks.run_checks_contract_support import write_checks_yaml


def test_run_checks_check_id_must_match_enabled_groups(tmp_path: Path) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["fitness"], check_id="smoke")
    assert not result.ok
    assert result.failed_check_id == "smoke"


def test_run_checks_validate_group_executes(tmp_path: Path) -> None:
    (tmp_path / "docs" / "spec" / "features").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "features" / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "docs" / "spec" / "features_done").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "features_done" / ".gitkeep").write_text(
        "",
        encoding="utf-8",
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["validate"])
    assert result.ok


def test_run_checks_accepts_harness_phase_enum(tmp_path: Path) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase=HarnessCheckPhase.ITERATION_END)
    assert result.ok


def test_run_checks_rejects_run_shell_command_kwarg(tmp_path: Path) -> None:
    untyped_run_checks = cast(Any, run_checks)
    with pytest.raises(TypeError, match="unexpected keyword argument 'run_shell_command'"):
        untyped_run_checks(
            tmp_path,
            phase="iteration_end",
            run_shell_command=lambda _root, _command: SimpleNamespace(returncode=0),
        )


def test_run_checks_reports_parse_failures_without_raising(tmp_path: Path) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi | cat",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert "[check:smoke] returncode=2" in result.output
    assert "shell syntax is not supported" in result.output
    assert "Remediation: provide a plain argv-style command" in result.output


def test_run_checks_allows_literal_shell_like_command_arguments(tmp_path: Path) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo $HOME ${HOME} `uname`",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert result.ok
    assert "[check:smoke] returncode=0" in result.output
    stdout = result.output.split("[check:smoke] returncode=0", 1)[1].lstrip()
    assert stdout.splitlines()[0] == "$HOME ${HOME} `uname`"


def test_run_checks_rejects_shell_chaining_without_partial_execution(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "checks-shell-chaining-marker.txt"
    command = f"touch {marker_path.as_posix()} && echo should-not-run"
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                f"    command: {command}",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert "[check:smoke] returncode=2" in result.output
    assert "shell syntax is not supported" in result.output
    assert "Remediation: provide a plain argv-style command" in result.output
    assert not marker_path.exists()


def test_run_checks_rejects_shell_redirection_without_partial_execution(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "checks-shell-redirection-marker.txt"
    redirected_path = tmp_path / "checks-shell-redirection.out"
    command = f"touch {marker_path.as_posix()} > {redirected_path.as_posix()}"
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                f"    command: {command}",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert "[check:smoke] returncode=2" in result.output
    assert "shell syntax is not supported" in result.output
    assert "Remediation: provide a plain argv-style command" in result.output
    assert not marker_path.exists()
    assert not redirected_path.exists()


def test_run_checks_reports_missing_executable_without_raising(tmp_path: Path) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: missing-executable-for-feat-159",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert "[check:smoke] returncode=127" in result.output
    assert "command executable not found: missing-executable-for-feat-159" in result.output
    assert "Remediation: install the executable" in result.output


def test_run_checks_command_prompt_feedback_includes_command_returncode_and_excerpt(
    tmp_path: Path,
) -> None:
    command = 'python -c "print(1); import sys; sys.exit(3)"'
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                f"    command: '{command}'",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert result.prompt_feedback is not None
    assert f"- command: `{command}`" in result.prompt_feedback
    assert "- returncode: 3" in result.prompt_feedback
    assert "- failure_output_excerpt:" in result.prompt_feedback
    assert "  1" in result.prompt_feedback


def test_run_checks_exposes_structured_command_invocations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_checks_yaml(
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

    def run_shell_command(_root: Path, _command: str) -> object:
        return SimpleNamespace(returncode=0, stdout="hi\n", stderr="")

    monkeypatch.setattr(
        "engineeringagent.adapters.quality.check_strategies.run_shell_command",
        run_shell_command,
        raising=True,
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert result.ok
    assert len(result.command_invocations) == 1
    invocation = result.command_invocations[0]
    assert invocation.check_id == "smoke"
    assert invocation.command == "echo hi"
    assert invocation.returncode == 0
    assert invocation.duration_ms >= 0


def test_run_checks_dry_run_is_decisions_only_and_side_effect_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_checks_yaml(
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

    def should_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("command execution must not happen in dry-run")

    monkeypatch.setattr(
        "engineeringagent.adapters.quality.check_strategies.run_shell_command",
        should_not_run,
        raising=True,
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"], dry_run=True)

    assert result.ok
    assert result.dry_run is True
    assert len(result.decisions) == 1
    assert result.decisions[0]["check_id"] == "smoke"
    assert result.executions == ()
    assert result.failed_check_id is None
