from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from engineeringagent import agents


def test_agents_module_exports_backend_agnostic_helpers() -> None:
    assert callable(agents.preflight)
    assert callable(agents.describe_action)
    assert callable(agents.classify_backend_exception)


def test_preflight_uses_opencode_probe_for_default_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Result:
        ok = True

    called: list[Path] = []

    def _fake_probe(project_root: Path) -> _Result:
        called.append(project_root)
        return _Result()

    monkeypatch.setattr(
        "engineeringagent.agents.helpers.run_permission_probe", _fake_probe
    )

    assert agents.preflight(tmp_path) is True
    assert called == [tmp_path]


def test_preflight_noops_for_non_opencode_backends(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "custom"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "engineeringagent.agents.registry._BACKEND_FACTORIES",
        {"custom": lambda structured: structured},
    )

    assert agents.preflight(tmp_path) is True


def test_describe_action_returns_stable_opencode_label(tmp_path: Path) -> None:
    assert (
        agents.describe_action(tmp_path, action="implement", structured=False)
        == "opencode run --agent engineeringagent"
    )


def test_describe_action_includes_json_format_when_structured(tmp_path: Path) -> None:
    assert (
        agents.describe_action(tmp_path, action="selector", structured=True)
        == "opencode run --agent engineeringagent --format json"
    )


def test_describe_action_falls_back_to_backend_and_action_for_unknown_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "custom"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "engineeringagent.agents.registry._BACKEND_FACTORIES",
        {"custom": lambda structured: structured},
    )

    assert (
        agents.describe_action(tmp_path, action="implement", structured=False)
        == "custom run implement"
    )


def test_classify_backend_exception_maps_permission_rejections() -> None:
    exc = agents.AgentBackendError(
        backend="opencode",
        message="boom",
        process=agents.AgentBackendFailureDetails(
            returncode=1,
            stderr="error: permission requested: bash\n",
        ),
    )

    failed_gate, message = agents.classify_backend_exception(exc)
    assert failed_gate == "opencode_permission"
    assert "permission requested" in message


def test_classify_backend_exception_maps_file_not_found() -> None:
    failed_gate, message = agents.classify_backend_exception(FileNotFoundError())
    assert failed_gate == "agent_missing"
    assert "executable missing" in message


def test_classify_backend_exception_maps_timeout() -> None:
    failed_gate, message = agents.classify_backend_exception(
        subprocess.TimeoutExpired(cmd=["opencode"], timeout=5)
    )
    assert failed_gate == "agent_timeout"
    assert "timed out" in message


def test_classify_backend_exception_maps_generic_backend_error() -> None:
    exc = agents.AgentBackendError(
        backend="custom",
        message="boom",
        process=agents.AgentBackendFailureDetails(returncode=1, stderr="bad"),
    )
    failed_gate, message = agents.classify_backend_exception(exc)
    assert failed_gate == "custom_build"
    assert message == "bad"


def test_classify_backend_exception_maps_unknown_exception_type() -> None:
    failed_gate, message = agents.classify_backend_exception(RuntimeError("boom"))
    assert failed_gate == "agent_error"
    assert message == "boom"


def test_describe_action_rejects_empty_action(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="action must be a non-empty string"):
        agents.describe_action(tmp_path, action="", structured=False)


def test_classify_backend_exception_uses_exception_name_when_message_missing() -> None:
    class _CustomError(Exception):
        def __str__(self) -> str:
            return ""

    failed_gate, message = agents.classify_backend_exception(_CustomError())
    assert failed_gate == "agent_error"
    assert message == "_CustomError"
