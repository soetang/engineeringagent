from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel

from engineeringagent import agents
from engineeringagent.agents.contracts import AgentRunRequest
from engineeringagent.adapters.agents import registry as registry_module
from engineeringagent.adapters.agents.registry import get_backend_factory
from engineeringagent.adapters.agents.runtime import resolve_agent_strategy
import engineeringagent.adapters.agents.runtime as agents_runtime_module


@dataclass(frozen=True)
class _StubBackend:
    _name: str = "stub"

    @property
    def name(self) -> str:
        """Return the backend name."""
        return self._name

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> agents.AgentBackendRunResult:
        """Return a deterministic echo result."""
        assert project_root.exists()
        assert session_id is None
        return agents.AgentBackendRunResult(text=f"echo:{prompt}")

    def run_request(self, request: AgentRunRequest) -> Any:
        return self.run(request.project_root, request.prompt).text


class _SequencedBackend:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.session_ids: list[str | None] = []

    @property
    def name(self) -> str:
        """Return the backend name."""
        return "sequenced"

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> agents.AgentBackendRunResult:
        """Record inputs and return deterministic text."""
        assert project_root.exists()
        self.prompts.append(prompt)
        self.session_ids.append(session_id)
        return agents.AgentBackendRunResult(
            text=f"echo:{prompt}", session_id=session_id
        )

    def run_request(self, request: AgentRunRequest) -> Any:
        return self.run(request.project_root, request.prompt).text


@dataclass(frozen=True)
class _ConfiguredBackend:
    @property
    def name(self) -> str:
        """Return backend name used in validation errors."""
        return "configured"

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> agents.AgentBackendRunResult:
        """Return a deterministic backend-specific response."""
        assert project_root.exists()
        assert session_id is None
        return agents.AgentBackendRunResult(text=f"configured:{prompt}")

    def run_request(self, request: AgentRunRequest) -> Any:
        return self.run(request.project_root, request.prompt).text


def _configured_backend_factory() -> agents.AgentBackend:
    return _ConfiguredBackend()


def _configure_backend(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend_id: str,
    backend_factory: Any,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        f'[agents]\nbackend = "{backend_id}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        registry_module,
        "_BACKEND_FACTORIES",
        {backend_id: backend_factory},
    )


def test_agents_module_exports_run_agent() -> None:
    """Expose the public run-agent helper from the package root."""
    assert callable(agents.run_agent)


def test_agents_module_exports_list_backends() -> None:
    """Expose backend discovery from the package root."""
    assert callable(agents.list_backends)


def test_agents_module_exports_resolve_backend_id() -> None:
    """Expose backend-id resolution from the package root."""
    assert callable(agents.resolve_backend_id)


def test_agents_module_exports_build_backend_scaffold_manifest() -> None:
    """Expose scaffold manifest generation from the package root."""
    assert callable(agents.build_backend_scaffold_manifest)


def test_list_backends_returns_stable_sorted_tuple() -> None:
    """Return a deterministic backend id listing for callers."""
    backend_ids = agents.list_backends()
    assert isinstance(backend_ids, tuple)
    assert backend_ids == tuple(sorted(backend_ids))
    assert "codex" in backend_ids
    assert "opencode" in backend_ids


def test_get_backend_factory_constructs_opencode_and_codex_backends() -> None:
    """Construct both built-in backend adapters from the registry."""
    opencode_factory = get_backend_factory("opencode")
    codex_factory = get_backend_factory("codex")

    opencode_backend = opencode_factory()
    codex_backend = codex_factory()

    assert opencode_backend.name == "opencode"
    assert codex_backend.name == "codex"


def test_get_backend_factory_raises_for_unknown_backend_id() -> None:
    """Reject unknown backend ids with a stable error."""
    with pytest.raises(ValueError, match=r"unknown agent backend id"):
        get_backend_factory("missing")


def test_resolve_backend_id_defaults_to_opencode_when_unset(tmp_path: Path) -> None:
    """Fall back to the registered default backend when config is absent."""
    assert agents.resolve_backend_id(tmp_path) == "opencode"


def test_build_backend_scaffold_manifest_for_opencode() -> None:
    """Render the bundled scaffold manifest for OpenCode."""
    manifest = agents.build_backend_scaffold_manifest(
        backend_id="opencode",
        agent_model="openai/gpt-5.3-codex-spark",
    )

    assert sorted(manifest) == [
        ".opencode/.gitignore",
        ".opencode/agents/engineeringagent.md",
    ]
    assert manifest[".opencode/.gitignore"]
    assert manifest[".opencode/.gitignore"].endswith("\n")
    assert manifest[".opencode/agents/engineeringagent.md"]


def test_build_backend_scaffold_manifest_for_codex() -> None:
    """Render the bundled scaffold manifest for Codex."""
    manifest = agents.build_backend_scaffold_manifest(
        backend_id="codex",
        agent_model="openai/gpt-5.3-codex-spark",
    )

    assert sorted(manifest) == [".codex/config.toml"]
    assert "[profiles.engineeringagent]" in manifest[".codex/config.toml"]
    assert 'model = "gpt-5.3-codex-spark"' in manifest[".codex/config.toml"]
    assert 'approval_policy = "never"' in manifest[".codex/config.toml"]


def test_build_backend_scaffold_manifest_raises_for_unknown_backend() -> None:
    """Reject scaffold generation for unknown backend ids."""
    with pytest.raises(ValueError, match=r"unknown agent backend id") as excinfo:
        agents.build_backend_scaffold_manifest(
            backend_id="missing",
            agent_model="openai/gpt-5.3-codex",
        )

    message = str(excinfo.value)
    assert "available backends" in message
    assert "opencode" in message


def test_default_backend_id_raises_when_default_not_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard against registry corruption removing the default backend."""
    monkeypatch.setattr(registry_module, "_DEFAULT_BACKEND_ID", "missing")

    with pytest.raises(ValueError, match=r"default agent backend id is not registered"):
        agents.default_backend_id()


def test_resolve_backend_id_prefers_engineeringagent_toml_over_pyproject(
    tmp_path: Path,
) -> None:
    """Prefer dedicated repo config over the pyproject fallback."""
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "opencode"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.agents]\nbackend = "missing"\n',
        encoding="utf-8",
    )

    assert agents.resolve_backend_id(tmp_path) == "opencode"


def test_run_agent_returns_text_for_str_output_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return plain text when the request asks for string output."""
    backend = _StubBackend()
    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="stub",
        backend_factory=lambda: backend,
    )
    assert agents.run_agent(tmp_path, "hi", output_type=str) == "echo:hi"


def test_run_agent_uses_configured_backend_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolve the backend from dedicated repo config by default."""
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "configured"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        registry_module,
        "_BACKEND_FACTORIES",
        {"configured": _configured_backend_factory},
    )

    assert agents.run_agent(tmp_path, "hi") == "configured:hi"


def test_run_agent_uses_pyproject_configured_backend_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolve the backend from the pyproject fallback when needed."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.agents]\nbackend = "configured"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        registry_module,
        "_BACKEND_FACTORIES",
        {"configured": _configured_backend_factory},
    )

    assert agents.run_agent(tmp_path, "hi") == "configured:hi"


def test_run_agent_delegates_to_runtime_request_for_text_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build the canonical request envelope for text execution."""
    calls: list[AgentRunRequest] = []

    def _run_agent_request(request: AgentRunRequest) -> Any:
        calls.append(request)
        return "echo:hi"

    monkeypatch.setattr(
        agents_runtime_module,
        "run_agent_request",
        _run_agent_request,
    )

    assert agents.run_agent(tmp_path, "hi", output_type=str) == "echo:hi"
    assert calls == [
        AgentRunRequest(project_root=tmp_path, prompt="hi", output_type=str)
    ]


def test_run_agent_delegates_to_runtime_request_for_structured_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build the canonical request envelope for structured execution."""
    class _Payload(BaseModel):
        value: int

    calls: list[AgentRunRequest] = []

    def _run_agent_request(request: AgentRunRequest) -> Any:
        calls.append(request)
        return _Payload(value=9)

    monkeypatch.setattr(
        agents_runtime_module,
        "run_agent_request",
        _run_agent_request,
    )

    parsed = cast(
        Any,
        agents.run_agent(
            tmp_path,
            "return value",
            output_type=_Payload,
            max_validation_retries=4,
        ),
    )

    assert parsed.value == 9
    assert calls == [
        AgentRunRequest(
            project_root=tmp_path,
            prompt="return value",
            output_type=_Payload,
            max_validation_retries=4,
        )
    ]


def test_resolve_agent_strategy_returns_configured_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Instantiate the configured backend strategy once per request."""
    backend = _SequencedBackend()
    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda: backend,
    )

    strategy = resolve_agent_strategy(tmp_path)
    assert strategy is backend


def test_run_agent_raises_for_unknown_configured_backend(tmp_path: Path) -> None:
    """Surface unknown configured backend ids to callers."""
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "missing"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"missing") as excinfo:
        agents.run_agent(tmp_path, "hi")

    message = str(excinfo.value)
    assert "available backends" in message
    assert "missing" in message
    assert "opencode" in message


def test_run_agent_rejects_backend_override_argument(tmp_path: Path) -> None:
    """Keep the public helper on the request-based configuration path."""
    with pytest.raises(TypeError, match=r"backend"):
        agents.run_agent(tmp_path, "hi", backend=object())  # type: ignore[call-arg]


def test_run_agent_rejects_negative_max_validation_retries(tmp_path: Path) -> None:
    """Reject invalid retry budgets before backend execution."""
    with pytest.raises(ValueError, match=r"max_validation_retries must be >= 0"):
        agents.run_agent(tmp_path, "hi", max_validation_retries=-1)


def test_agent_output_validation_error_exposes_debug_fields() -> None:
    """Expose stable debugging fields on validation failures."""
    err = agents.AgentOutputValidationError(
        backend="stub",
        attempts=3,
        last_text="raw",
        error_summary="bad json",
        backend_metadata={"session_id": "s1"},
    )
    assert err.backend == "stub"
    assert err.attempts == 3
    assert err.last_text == "raw"
    assert err.error_summary == "bad json"
    assert err.backend_metadata["session_id"] == "s1"


def test_agent_backend_error_exposes_failure_details() -> None:
    """Expose stable process diagnostics on backend failures."""
    details = agents.AgentBackendFailureDetails(
        returncode=2,
        stdout="hello\n",
        stderr="world\n",
        command_args=["opencode", "run"],
    )
    err = agents.AgentBackendError(
        backend="stub",
        message="boom",
        process=details,
        backend_metadata={"session_id": "s1"},
    )
    assert err.backend == "stub"
    assert err.message == "boom"
    assert err.returncode == 2
    assert err.command_args == ["opencode", "run"]
    assert err.output == "hello\nworld\n"
    assert err.backend_metadata["session_id"] == "s1"
