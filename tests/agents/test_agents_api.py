from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel, create_model

from engineeringagent import agents


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


class _SequencedBackend:
    def __init__(self, *, results: list[agents.AgentBackendRunResult]) -> None:
        self._results = list(results)
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
        """Return the next queued result and record inputs."""
        assert project_root.exists()
        self.prompts.append(prompt)
        self.session_ids.append(session_id)
        if not self._results:
            raise RuntimeError("no more stub results")
        return self._results.pop(0)


def test_agents_module_exports_run_agent() -> None:
    assert callable(agents.run_agent)


def test_agents_module_exports_list_backends() -> None:
    assert callable(agents.list_backends)


def test_agents_module_exports_resolve_backend_id() -> None:
    assert callable(agents.resolve_backend_id)


def test_agents_module_exports_build_backend_scaffold_manifest() -> None:
    assert callable(agents.build_backend_scaffold_manifest)


def test_list_backends_returns_stable_sorted_tuple() -> None:
    backend_ids = agents.list_backends()
    assert isinstance(backend_ids, tuple)
    assert backend_ids == tuple(sorted(backend_ids))
    assert "opencode" in backend_ids


def test_resolve_backend_id_defaults_to_opencode_when_unset(tmp_path: Path) -> None:
    assert agents.resolve_backend_id(tmp_path) == "opencode"


def test_build_backend_scaffold_manifest_for_opencode() -> None:
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


def test_build_backend_scaffold_manifest_raises_for_unknown_backend() -> None:
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
    monkeypatch.setattr(
        "engineeringagent.agents.registry._DEFAULT_BACKEND_ID", "missing"
    )

    with pytest.raises(ValueError, match=r"default agent backend id is not registered"):
        agents.default_backend_id()


def test_resolve_backend_id_prefers_engineeringagent_toml_over_pyproject(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "opencode"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.agents]\nbackend = "missing"\n',
        encoding="utf-8",
    )

    assert agents.resolve_backend_id(tmp_path) == "opencode"


def test_run_agent_returns_text_for_str_output_type(tmp_path: Path) -> None:
    backend = _StubBackend()
    assert (
        agents.run_agent(tmp_path, "hi", backend=backend, output_type=str) == "echo:hi"
    )


def test_run_agent_uses_configured_backend_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    def _create_configured_backend(structured_output: bool) -> agents.AgentBackend:
        assert structured_output is False
        return _ConfiguredBackend()

    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "configured"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "engineeringagent.agents.registry._BACKEND_FACTORIES",
        {"configured": _create_configured_backend},
    )

    assert agents.run_agent(tmp_path, "hi") == "configured:hi"


def test_run_agent_uses_pyproject_configured_backend_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    def _create_configured_backend(structured_output: bool) -> agents.AgentBackend:
        assert structured_output is False
        return _ConfiguredBackend()

    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.agents]\nbackend = "configured"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "engineeringagent.agents.registry._BACKEND_FACTORIES",
        {"configured": _create_configured_backend},
    )

    assert agents.run_agent(tmp_path, "hi") == "configured:hi"


def test_run_agent_raises_for_unknown_configured_backend(tmp_path: Path) -> None:
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


def test_run_agent_rejects_negative_max_validation_retries(tmp_path: Path) -> None:
    backend = _StubBackend()
    with pytest.raises(ValueError, match=r"max_validation_retries must be >= 0"):
        agents.run_agent(tmp_path, "hi", backend=backend, max_validation_retries=-1)


def test_run_agent_structured_output_validates_and_returns_model(
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(
                text=json.dumps({"value": 3}, sort_keys=True, ensure_ascii=True),
                session_id=None,
            ),
        ]
    )
    parsed = agents.run_agent(tmp_path, "hi", backend=backend, output_type=_Payload)
    assert parsed.value == 3


def test_run_agent_structured_output_retries_in_same_session_on_invalid_json(
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        ok: bool

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text="not json", session_id="s1"),
            agents.AgentBackendRunResult(text='{"ok":true}', session_id="s1"),
        ]
    )

    parsed = agents.run_agent(
        tmp_path,
        "hi",
        backend=backend,
        output_type=_Payload,
        max_validation_retries=1,
    )
    assert parsed.ok is True
    assert backend.session_ids == [None, "s1"]
    assert str(tmp_path) not in backend.prompts[1]


def test_run_agent_structured_output_retries_on_schema_mismatch(tmp_path: Path) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text='{"value":"nope"}', session_id="s1"),
            agents.AgentBackendRunResult(text='{"value":1}', session_id="s1"),
        ]
    )

    parsed = agents.run_agent(
        tmp_path,
        "hi",
        backend=backend,
        output_type=_Payload,
        max_validation_retries=1,
    )
    assert parsed.value == 1
    assert backend.session_ids == [None, "s1"]


def test_run_agent_structured_output_raises_typed_error_after_retries(
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text="not json", session_id="s1"),
            agents.AgentBackendRunResult(text="still not json", session_id="s1"),
        ]
    )

    with pytest.raises(agents.AgentOutputValidationError) as excinfo:
        agents.run_agent(
            tmp_path,
            "hi",
            backend=backend,
            output_type=_Payload,
            max_validation_retries=1,
        )
    err = excinfo.value
    assert err.backend == "sequenced"
    assert err.attempts == 2
    assert err.last_text == "still not json"


def test_run_agent_structured_retry_prompt_truncates_large_validation_error(
    tmp_path: Path,
) -> None:
    # Generate a large number of distinct validation errors so that the
    # deterministic retry prompt must truncate the error summary.
    create_model_any = cast(Any, create_model)
    payload_model = create_model_any(
        "Payload",
        **{f"f{i}": (int, ...) for i in range(250)},
    )

    bad = {f"f{i}": "nope" for i in range(250)}
    good = {f"f{i}": 1 for i in range(250)}

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text=json.dumps(bad), session_id="s1"),
            agents.AgentBackendRunResult(text=json.dumps(good), session_id="s1"),
        ]
    )

    parsed = agents.run_agent(
        tmp_path,
        "hi",
        backend=backend,
        output_type=payload_model,
        max_validation_retries=1,
    )
    assert getattr(parsed, "f0") == 1

    retry_prompt = backend.prompts[1]
    assert str(tmp_path) not in retry_prompt

    lines = retry_prompt.splitlines()
    error_index = lines.index("Error:")
    error_line = lines[error_index + 1]
    assert len(error_line) <= 500
    assert error_line.endswith("...")


def test_run_agent_structured_prompts_use_deterministic_wrapper(tmp_path: Path) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text='{"value":1}', session_id="s1"),
        ]
    )

    parsed = agents.run_agent(
        tmp_path, "do the thing", backend=backend, output_type=_Payload
    )
    assert parsed.value == 1

    initial = backend.prompts[0]
    assert initial.startswith("---\n")
    assert "Return exactly one strict JSON value" in initial
    assert "JSON Schema:" in initial
    assert "Task:" in initial
    assert initial.rstrip().endswith("---")


def test_run_agent_validation_error_truncates_last_text_when_huge(
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        value: int

    huge = "x" * 2100
    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text=huge, session_id="s1"),
            agents.AgentBackendRunResult(text=huge, session_id="s1"),
        ]
    )

    with pytest.raises(agents.AgentOutputValidationError) as excinfo:
        agents.run_agent(
            tmp_path,
            "hi",
            backend=backend,
            output_type=_Payload,
            max_validation_retries=1,
        )
    err = excinfo.value
    assert err.last_text is not None
    assert len(err.last_text) <= 2000
    assert err.last_text.endswith("...")


def test_agent_output_validation_error_exposes_debug_fields() -> None:
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
