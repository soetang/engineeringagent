from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from engineeringagent.opencode import client as client_module


def test_start_agent_runs_opencode_with_expected_defaults(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", fake_subprocess_run)

    result = client_module.start_agent(tmp_path, "Reply READY.")

    assert result.returncode == 0
    assert captured["command"] == [
        "opencode",
        "run",
        "--agent",
        "build",
        "Reply READY.",
    ]
    assert captured["kwargs"]["cwd"] == tmp_path
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True


def test_start_agent_supports_agent_override(tmp_path: Path, monkeypatch: Any) -> None:
    captured_command: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        captured_command.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", fake_subprocess_run)

    client_module.start_agent(tmp_path, "Do work", agent="review")

    assert captured_command == ["opencode", "run", "--agent", "review", "Do work"]
