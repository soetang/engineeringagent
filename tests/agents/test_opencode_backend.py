from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.agents import AgentBackendError
from engineeringagent.agents.backends.opencode import OpenCodeAgentBackend


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
        "engineeringagent.agents.backends.opencode.start_agent",
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
    def _fake_start_agent(project_root: Path, prompt: str, **kwargs: object) -> _Proc:
        return _Proc(returncode=1, stderr="boom")

    monkeypatch.setattr(
        "engineeringagent.agents.backends.opencode.start_agent",
        _fake_start_agent,
    )

    backend = OpenCodeAgentBackend(format="json")
    with pytest.raises(AgentBackendError, match=r"opencode run failed"):
        backend.run(tmp_path, "p")


def test_opencode_backend_raises_on_missing_text_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fake_start_agent(project_root: Path, prompt: str, **kwargs: object) -> _Proc:
        return _Proc(returncode=0, text_payload=None)

    monkeypatch.setattr(
        "engineeringagent.agents.backends.opencode.start_agent",
        _fake_start_agent,
    )

    backend = OpenCodeAgentBackend(format="json")
    with pytest.raises(AgentBackendError, match=r"missing final text payload"):
        backend.run(tmp_path, "p")
