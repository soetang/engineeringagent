from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from engineeringagent.agents import AgentBackendError
from engineeringagent.adapters.agents.opencode import OpenCodeAgentBackend
from engineeringagent.adapters.agents.opencode import client as client_module
from engineeringagent.agents.contracts import AgentRunRequest


class _Proc:
    def __init__(
        self,
        *,
        args: list[str] | None = None,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        text_payload: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.args = args or ["opencode", "run"]
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.text_payload = text_payload
        self.session_id = session_id


def test_opencode_backend_happy_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, str, dict[str, object]]] = []

    def _fake_start_agent(project_root: Path, prompt: str, **kwargs: object) -> _Proc:
        calls.append((project_root, prompt, kwargs))
        return _Proc(
            returncode=0,
            text_payload="hello",
            session_id="s1",
        )

    monkeypatch.setattr(
        "engineeringagent.adapters.agents.opencode.backend.start_agent",
        _fake_start_agent,
    )

    backend = OpenCodeAgentBackend(agent="a1", format="json")
    result = backend.run(tmp_path, "p1", session_id="s0")

    assert backend.name == "opencode"
    assert result.text == "hello"
    assert result.session_id == "s1"
    assert calls == [
        (
            tmp_path,
            "p1",
            {
                "agent": "a1",
                "format": "json",
                "session": "s0",
            },
        )
    ]


def test_opencode_backend_raises_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fake_start_agent(
        _project_root: Path, _prompt: str, **_kwargs: object
    ) -> _Proc:
        return _Proc(returncode=1, stderr="boom")

    monkeypatch.setattr(
        "engineeringagent.adapters.agents.opencode.backend.start_agent",
        _fake_start_agent,
    )

    backend = OpenCodeAgentBackend(format="json")
    with pytest.raises(AgentBackendError, match=r"opencode run failed"):
        backend.run(tmp_path, "p")


def test_opencode_backend_raises_on_missing_text_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fake_start_agent(
        _project_root: Path, _prompt: str, **_kwargs: object
    ) -> _Proc:
        return _Proc(returncode=0, text_payload=None)

    monkeypatch.setattr(
        "engineeringagent.adapters.agents.opencode.backend.start_agent",
        _fake_start_agent,
    )

    backend = OpenCodeAgentBackend(format="json")
    with pytest.raises(AgentBackendError, match=r"missing final text payload"):
        backend.run(tmp_path, "p")


def test_opencode_backend_keeps_hyphen_prompt_as_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def _fake_subprocess_run(
        command: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    backend = OpenCodeAgentBackend()
    result = backend.run(tmp_path, "--- reviewer payload")

    assert result.text == "ok"
    assert captured["command"] == [
        "opencode",
        "run",
        "--agent",
        "engineeringagent",
        "--",
        "--- reviewer payload",
    ]


def test_opencode_backend_run_structured_retries_with_same_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        value: int

    calls: list[dict[str, object]] = []
    responses = [
        _Proc(returncode=0, text_payload="not json", session_id="s1"),
        _Proc(returncode=0, text_payload='{"value":2}', session_id="s1"),
    ]

    def _fake_start_agent(project_root: Path, prompt: str, **kwargs: object) -> _Proc:
        assert project_root == tmp_path
        calls.append(
            {
                "prompt": prompt,
                "session": kwargs.get("session"),
                "format": kwargs.get("format"),
            }
        )
        if not responses:
            raise RuntimeError("no more fake responses")
        return responses.pop(0)

    monkeypatch.setattr(
        "engineeringagent.adapters.agents.opencode.backend.start_agent",
        _fake_start_agent,
    )

    backend = OpenCodeAgentBackend(format="json")
    payload = backend.run_structured(
        tmp_path,
        "return json",
        output_type=_Payload,
        max_validation_retries=1,
    )

    assert payload.value == 2
    assert calls[0]["session"] is None
    assert calls[1]["session"] == "s1"


def test_opencode_backend_run_structured_rejects_negative_retry_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        value: int

    def _fail_if_called(*_args: object, **_kwargs: object) -> _Proc:
        raise AssertionError("start_agent should not be called")

    monkeypatch.setattr(
        "engineeringagent.adapters.agents.opencode.backend.start_agent",
        _fail_if_called,
    )

    backend = OpenCodeAgentBackend(format="json")
    with pytest.raises(ValueError, match=r"max_validation_retries must be >= 0"):
        backend.run_structured(
            tmp_path,
            "return json",
            output_type=_Payload,
            max_validation_retries=-1,
        )


def test_opencode_backend_run_request_text_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    def _fake_start_agent(_project_root: Path, _prompt: str, **kwargs: object) -> _Proc:
        calls.append(kwargs)
        return _Proc(returncode=0, stdout="plain")

    monkeypatch.setattr(
        "engineeringagent.adapters.agents.opencode.backend.start_agent",
        _fake_start_agent,
    )

    backend = OpenCodeAgentBackend(agent="a1")
    request = AgentRunRequest(project_root=tmp_path, prompt="say hi", output_type=str)

    assert backend.run_request(request) == "plain"
    assert calls == [{"agent": "a1", "format": None, "session": None}]


def test_opencode_backend_run_request_structured_mode_uses_backend_json_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        ok: bool

    calls: list[dict[str, object]] = []
    responses = [
        _Proc(returncode=0, text_payload="not json", session_id="s1"),
        _Proc(returncode=0, text_payload='{"ok": true}', session_id="s1"),
    ]

    def _fake_start_agent(project_root: Path, prompt: str, **kwargs: object) -> _Proc:
        assert project_root == tmp_path
        calls.append(
            {
                "prompt": prompt,
                "session": kwargs.get("session"),
                "format": kwargs.get("format"),
            }
        )
        if not responses:
            raise RuntimeError("no more fake responses")
        return responses.pop(0)

    monkeypatch.setattr(
        "engineeringagent.adapters.agents.opencode.backend.start_agent",
        _fake_start_agent,
    )

    backend = OpenCodeAgentBackend()

    request = AgentRunRequest(
        project_root=tmp_path,
        prompt="return envelope",
        output_type=_Payload,
        max_validation_retries=1,
    )

    parsed = backend.run_request(request)
    assert parsed.ok is True
    assert len(calls) == 2
    assert calls[0]["format"] == "json"
    assert calls[0]["session"] is None
    assert calls[1]["session"] == "s1"
