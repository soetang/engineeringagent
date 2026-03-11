from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from engineeringagent.adapters.vcs import git_cli
from engineeringagent.adapters.vcs.git_cli import diff_name_status


@pytest.mark.parametrize(
    ("hook_type", "expected_command"),
    [
        (None, ["pre-commit", "install"]),
        ("commit-msg", ["pre-commit", "install", "--hook-type", "commit-msg"]),
    ],
)
def test_precommit_install_invokes_subprocess_non_interactive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hook_type: str | None,
    expected_command: list[str],
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _fake_run(cmd: list[str], **kwargs: object) -> object:
        calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(git_cli.subprocess, "run", _fake_run)

    git_cli.precommit_install(tmp_path, hook_type=hook_type)

    assert len(calls) == 1
    cmd, kwargs = calls[0]
    assert cmd == expected_command
    assert kwargs["cwd"] == tmp_path
    assert kwargs["stdin"] is git_cli.subprocess.DEVNULL
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False


def test_diff_name_status_includes_base_and_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_cli.subprocess.run",
        _run,
        raising=True,
    )

    result = diff_name_status(tmp_path, base="main", head="feature")

    assert result.returncode == 0
    assert captured["args"] == (
        [
            "git",
            "diff",
            "--name-status",
            "--find-renames",
            "--diff-filter=AMDR",
            "main",
            "feature",
        ],
    )
    assert captured["kwargs"] == {
        "cwd": tmp_path,
        "capture_output": True,
        "text": True,
        "check": False,
    }
