from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from engineeringagent.git import client as client_module


def test_status_porcelain_runs_expected_git_command(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", fake_subprocess_run)

    client_module.status_porcelain(tmp_path)

    assert captured["command"] == ["git", "status", "--porcelain"]
    assert captured["kwargs"]["cwd"] == tmp_path
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True


def test_head_short_runs_expected_git_command(tmp_path: Path, monkeypatch: Any) -> None:
    captured_command: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        captured_command.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="abc123\n", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", fake_subprocess_run)

    result = client_module.head_short(tmp_path)

    assert result.stdout == "abc123\n"
    assert captured_command == ["git", "rev-parse", "--short", "HEAD"]


def test_add_all_runs_expected_git_command(tmp_path: Path, monkeypatch: Any) -> None:
    captured_command: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        captured_command.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", fake_subprocess_run)

    client_module.add_all(tmp_path)

    assert captured_command == ["git", "add", "-A", "--", "."]


def test_commit_runs_expected_git_command(tmp_path: Path, monkeypatch: Any) -> None:
    captured_command: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        captured_command.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", fake_subprocess_run)

    client_module.commit(tmp_path, "feat: complete FEAT-999")

    assert captured_command == [
        "git",
        "-c",
        "user.name=engineeringagent",
        "-c",
        "user.email=engineeringagent@local",
        "commit",
        "-m",
        "feat: complete FEAT-999",
    ]
