from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

from engineeringagent.agents.backends.opencode import client as client_module


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
    assert result.stdout == "ok\n"
    assert result.stderr == ""
    assert captured["command"] == [
        "opencode",
        "run",
        "--agent",
        "engineeringagent",
        "--",
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

    assert captured_command == [
        "opencode",
        "run",
        "--agent",
        "review",
        "--",
        "Do work",
    ]


def test_start_agent_inserts_separator_before_hyphen_leading_prompt(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured_command: list[str] = []

    def fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        captured_command.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", fake_subprocess_run)

    client_module.start_agent(
        tmp_path,
        "--- hello",
        agent="engineeringagent",
        format="json",
        session="sess-7",
    )

    assert captured_command == [
        "opencode",
        "run",
        "--session",
        "sess-7",
        "--format",
        "json",
        "--agent",
        "engineeringagent",
        "--",
        "--- hello",
    ]


def test_start_agent_parses_json_format_into_structured_fields(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    def fake_subprocess_run(
        command: Any, **_kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="\n".join(
                [
                    '{"type":"start","sessionID":"sess-123"}',
                    '{"type":"text","part":{"text":"first"}}',
                    '{"type":"text","part":{"text":"second"}}',
                    "",
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(client_module.subprocess, "run", fake_subprocess_run)

    result = client_module.start_agent(tmp_path, "hello", format="json")

    assert result.returncode == 0
    assert result.session_id == "sess-123"
    assert result.text_payload == "second"


def test_default_agent_constant_matches_expected_runtime_identifier() -> None:
    assert client_module.DEFAULT_OPENCODE_AGENT == "engineeringagent"


def test_legacy_agents_defaults_module_is_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("engineeringagent.agents_defaults")
