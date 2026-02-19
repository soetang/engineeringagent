from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel, ConfigDict, create_model

from engineeringagent import agents
from engineeringagent.agents import api as agents_api_module
from engineeringagent.agents import registry as registry_module
from engineeringagent.agents.backends.codex import backend as codex_backend_module
from engineeringagent.agents.backends.codex import client as codex_client
from engineeringagent.agents.backends.opencode import backend as opencode_backend_module
from engineeringagent.agents.backends.opencode import client as opencode_client
from engineeringagent.agents.runtime import (
    PromptRetryStructuredStrategy,
    resolve_agent_strategy,
)
from engineeringagent.agents.registry import get_backend_factory
from engineeringagent.checks.reviewers.engine import ReviewerDecisionEnvelope


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


class _StructuredStrategyBackend:
    def __init__(self, *, structured_result: Any) -> None:
        """Store deterministic structured result and call log."""
        self.structured_result = structured_result
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        """Return backend name used in typed errors."""
        return "structured-strategy"

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> agents.AgentBackendRunResult:
        """Fail fast when text path is used unexpectedly."""
        del project_root, prompt, session_id
        raise AssertionError("run() should not be used for structured outputs")

    def run_structured(
        self,
        project_root: Path,
        prompt: str,
        *,
        output_type: Any,
        max_validation_retries: int,
    ) -> Any:
        """Record call arguments and return pre-validated payload."""
        assert project_root.exists()
        self.calls.append(
            {
                "prompt": prompt,
                "output_type": output_type,
                "max_validation_retries": max_validation_retries,
            }
        )
        return self.structured_result


class _DelegatingBackend:
    @property
    def name(self) -> str:
        """Return backend name used by resolver delegation tests."""
        return "delegating"

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> agents.AgentBackendRunResult:
        """Return deterministic text while preserving session id."""
        assert project_root.exists()
        return agents.AgentBackendRunResult(
            text=f"delegated:{prompt}",
            session_id=session_id,
        )


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


def _configured_backend_factory(structured_output: bool) -> agents.AgentBackend:
    assert structured_output is False
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
    assert "codex" in backend_ids
    assert "opencode" in backend_ids


def test_get_backend_factory_constructs_opencode_and_codex_backends() -> None:
    opencode_factory = get_backend_factory("opencode")
    codex_factory = get_backend_factory("codex")

    opencode_backend = opencode_factory(True)
    codex_backend = codex_factory(False)

    assert opencode_backend.name == "opencode"
    assert codex_backend.name == "codex"


def test_get_backend_factory_raises_for_unknown_backend_id() -> None:
    with pytest.raises(ValueError, match=r"unknown agent backend id"):
        get_backend_factory("missing")


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


def test_build_backend_scaffold_manifest_for_codex() -> None:
    manifest = agents.build_backend_scaffold_manifest(
        backend_id="codex",
        agent_model="openai/gpt-5.3-codex-spark",
    )

    assert sorted(manifest) == [".codex/config.toml"]
    assert "[profiles.engineeringagent]" in manifest[".codex/config.toml"]
    assert 'model = "gpt-5.3-codex-spark"' in manifest[".codex/config.toml"]
    assert 'approval_policy = "never"' in manifest[".codex/config.toml"]


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
    monkeypatch.setattr(registry_module, "_DEFAULT_BACKEND_ID", "missing")

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


def test_run_agent_returns_text_for_str_output_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _StubBackend()
    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="stub",
        backend_factory=lambda structured_output: backend,
    )
    assert agents.run_agent(tmp_path, "hi", output_type=str) == "echo:hi"


def test_run_agent_uses_configured_backend_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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


def test_run_agent_uses_strategy_resolver_for_text_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _StubBackend(_name="resolved")
    calls: list[dict[str, Any]] = []

    def _resolve_agent_strategy(
        project_root: Path,
        *,
        structured_output: bool,
    ) -> agents.AgentBackend:
        calls.append(
            {
                "project_root": project_root,
                "structured_output": structured_output,
            }
        )
        return backend

    monkeypatch.setattr(
        agents_api_module,
        "resolve_agent_strategy",
        _resolve_agent_strategy,
    )

    assert agents.run_agent(tmp_path, "hi", output_type=str) == "echo:hi"
    assert calls == [
        {
            "project_root": tmp_path,
            "structured_output": False,
        }
    ]


def test_run_agent_uses_strategy_resolver_for_structured_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _StructuredStrategyBackend(structured_result=_Payload(value=9))
    calls: list[dict[str, Any]] = []

    def _resolve_agent_strategy(
        project_root: Path,
        *,
        structured_output: bool,
    ) -> agents.StructuredOutputAgentBackend:
        calls.append(
            {
                "project_root": project_root,
                "structured_output": structured_output,
            }
        )
        return backend

    monkeypatch.setattr(
        agents_api_module,
        "resolve_agent_strategy",
        _resolve_agent_strategy,
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
        {
            "project_root": tmp_path,
            "structured_output": True,
        }
    ]
    assert backend.calls == [
        {
            "prompt": "return value",
            "output_type": _Payload,
            "max_validation_retries": 4,
        }
    ]


def test_resolve_agent_strategy_wraps_plain_backend_for_structured_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text='{"value":1}', session_id="s1"),
        ]
    )
    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )

    strategy = resolve_agent_strategy(tmp_path, structured_output=True)
    assert isinstance(strategy, agents.StructuredOutputAgentBackend)

    parsed = strategy.run_structured(
        tmp_path,
        "hi",
        output_type=_Payload,
        max_validation_retries=1,
    )
    assert parsed.value == 1


def test_prompt_retry_structured_strategy_run_delegates_text_call(
    tmp_path: Path,
) -> None:
    strategy = PromptRetryStructuredStrategy(_DelegatingBackend())

    result = strategy.run(tmp_path, "hi", session_id="s1")

    assert result.text == "delegated:hi"
    assert result.session_id == "s1"


def test_prompt_retry_structured_strategy_empty_output_raises_typed_error(
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _SequencedBackend(results=[agents.AgentBackendRunResult(text="")])
    strategy = PromptRetryStructuredStrategy(backend)

    with pytest.raises(agents.AgentOutputValidationError) as excinfo:
        strategy.run_structured(
            tmp_path,
            "return json",
            output_type=_Payload,
            max_validation_retries=0,
        )

    err = excinfo.value
    assert err.backend == "sequenced"
    assert err.error_summary == "output is empty"
    assert err.last_text is None


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


def test_run_agent_rejects_backend_override_argument(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match=r"backend"):
        agents.run_agent(tmp_path, "hi", backend=object())  # type: ignore[call-arg]


def test_run_agent_rejects_negative_max_validation_retries(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"max_validation_retries must be >= 0"):
        agents.run_agent(tmp_path, "hi", max_validation_retries=-1)


def test_run_agent_structured_output_validates_and_returns_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )
    parsed = cast(Any, agents.run_agent(tmp_path, "hi", output_type=_Payload))
    assert parsed.value == 3


def test_run_agent_structured_output_delegates_to_backend_strategy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _StructuredStrategyBackend(structured_result=_Payload(value=7))
    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="structured-strategy",
        backend_factory=lambda structured_output: backend,
    )

    parsed = cast(
        Any,
        agents.run_agent(
            tmp_path,
            "return value",
            output_type=_Payload,
            max_validation_retries=5,
        ),
    )

    assert parsed.value == 7
    assert backend.calls == [
        {
            "prompt": "return value",
            "output_type": _Payload,
            "max_validation_retries": 5,
        }
    ]


def test_run_agent_codex_structured_output_invokes_backend_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Payload(BaseModel):
        ok: bool

    calls: list[dict[str, Any]] = []

    def _fake_run_codex_exec(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> codex_client.CodexExecResult:
        calls.append(
            {
                "project_root": project_root,
                "prompt": prompt,
                "config": kwargs["config"],
            }
        )
        return codex_client.CodexExecResult(
            args=["codex", "exec", prompt],
            returncode=0,
            stdout="progress",
            stderr="",
            output_last_message='{"ok": true}',
        )

    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "codex"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        codex_backend_module,
        "run_codex_exec",
        _fake_run_codex_exec,
    )

    parsed = cast(
        Any,
        agents.run_agent(
            tmp_path,
            "return strict json",
            output_type=_Payload,
            max_validation_retries=7,
        ),
    )

    assert parsed.ok is True
    assert len(calls) == 1
    assert calls[0]["project_root"] == tmp_path
    assert calls[0]["prompt"] == "return strict json"
    assert calls[0]["config"].output_schema is not None


def test_run_agent_codex_structured_output_is_consumer_agnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _TaskSummary(BaseModel):
        ticket_id: int
        status: str

    calls: list[dict[str, Any]] = []

    def _fake_run_codex_exec(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> codex_client.CodexExecResult:
        calls.append(
            {
                "project_root": project_root,
                "prompt": prompt,
                "config": kwargs["config"],
            }
        )
        return codex_client.CodexExecResult(
            args=["codex", "exec", prompt],
            returncode=0,
            stdout="progress",
            stderr="",
            output_last_message='{"ticket_id": 12, "status": "done"}',
        )

    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "codex"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        codex_backend_module,
        "run_codex_exec",
        _fake_run_codex_exec,
    )

    parsed = cast(
        Any,
        agents.run_agent(
            tmp_path,
            "Summarize ticket 12 for release notes.",
            output_type=_TaskSummary,
        ),
    )

    assert parsed.ticket_id == 12
    assert parsed.status == "done"
    assert len(calls) == 1
    assert calls[0]["project_root"] == tmp_path
    assert calls[0]["prompt"] == "Summarize ticket 12 for release notes."
    assert "$responseformat" not in calls[0]["prompt"]
    output_schema = calls[0]["config"].output_schema
    assert isinstance(output_schema, dict)
    properties = output_schema.get("properties")
    assert isinstance(properties, dict)
    assert set(properties) == {"ticket_id", "status"}


def test_run_agent_codex_structured_output_validation_error_has_no_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Payload(BaseModel):
        model_config = ConfigDict(extra="forbid")

        ok: bool

    calls: list[str] = []

    def _fake_run_codex_exec(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> codex_client.CodexExecResult:
        del project_root, kwargs
        calls.append(prompt)
        return codex_client.CodexExecResult(
            args=["codex", "exec", prompt],
            returncode=0,
            stdout="progress",
            stderr="",
            output_last_message='{"ok": true, "extra": 1}',
        )

    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "codex"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        codex_backend_module,
        "run_codex_exec",
        _fake_run_codex_exec,
    )

    with pytest.raises(agents.AgentOutputValidationError) as excinfo:
        agents.run_agent(
            tmp_path,
            "return strict json",
            output_type=_Payload,
            max_validation_retries=7,
        )

    assert calls == ["return strict json"]
    assert excinfo.value.backend == "codex"
    assert excinfo.value.attempts == 1


def test_run_agent_opencode_structured_output_is_consumer_agnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _TaskSummary(BaseModel):
        ticket_id: int
        status: str

    calls: list[dict[str, Any]] = []

    def _fake_start_agent(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> opencode_client.OpenCodeAgentRunResult:
        calls.append(
            {
                "project_root": project_root,
                "prompt": prompt,
                "kwargs": kwargs,
            }
        )
        return opencode_client.OpenCodeAgentRunResult(
            args=["opencode", "run"],
            returncode=0,
            stdout="",
            stderr="",
            session_id="s1",
            text_payload='{"ticket_id": 12, "status": "done"}',
        )

    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "opencode"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        opencode_backend_module,
        "start_agent",
        _fake_start_agent,
    )

    parsed = cast(
        Any,
        agents.run_agent(
            tmp_path,
            "Summarize ticket 12 for release notes.",
            output_type=_TaskSummary,
        ),
    )

    assert parsed.ticket_id == 12
    assert parsed.status == "done"
    assert len(calls) == 1
    assert calls[0]["project_root"] == tmp_path
    assert calls[0]["kwargs"]["format"] == "json"
    wrapped_prompt = cast(str, calls[0]["prompt"])
    assert "$responseformat" not in wrapped_prompt


def test_run_agent_reviewer_envelope_accepts_single_strict_json_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(
                text=json.dumps(
                    {
                        "decision": "approve",
                        "summary": "Looks good.",
                        "required_actions": [],
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                ),
                session_id=None,
            ),
        ]
    )

    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )

    envelope = cast(
        ReviewerDecisionEnvelope,
        agents.run_agent(
            tmp_path,
            "Return reviewer decision envelope.",
            output_type=ReviewerDecisionEnvelope,
            max_validation_retries=0,
        ),
    )

    assert envelope.decision == "approve"
    assert envelope.summary == "Looks good."
    assert envelope.required_actions == []
    assert len(backend.prompts) == 1


def test_run_agent_reviewer_envelope_rejects_code_fenced_payload_with_bounded_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    huge_code_fenced_payload = "```json\n" + ("x" * 5000) + "\n```"
    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(
                text=huge_code_fenced_payload,
                session_id=None,
            ),
        ]
    )

    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )

    with pytest.raises(agents.AgentOutputValidationError) as excinfo:
        agents.run_agent(
            tmp_path,
            "Return reviewer decision envelope.",
            output_type=ReviewerDecisionEnvelope,
            max_validation_retries=0,
        )

    err = excinfo.value
    assert err.backend == "sequenced"
    assert err.attempts == 1
    assert err.error_summary.startswith("json parse error:")
    assert len(err.error_summary) <= 500
    assert err.last_text is not None
    assert len(err.last_text) <= 2000
    assert err.last_text.startswith("```json")
    assert err.last_text.endswith("...")


def test_run_agent_structured_output_retries_in_same_session_on_invalid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Payload(BaseModel):
        ok: bool

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text="not json", session_id="s1"),
            agents.AgentBackendRunResult(text='{"ok":true}', session_id="s1"),
        ]
    )

    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )

    parsed = cast(
        Any,
        agents.run_agent(
            tmp_path, "hi", output_type=_Payload, max_validation_retries=1
        ),
    )
    assert parsed.ok is True
    assert backend.session_ids == [None, "s1"]
    assert str(tmp_path) not in backend.prompts[1]


def test_run_agent_structured_output_retries_on_schema_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text='{"value":"nope"}', session_id="s1"),
            agents.AgentBackendRunResult(text='{"value":1}', session_id="s1"),
        ]
    )

    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )

    parsed = cast(
        Any,
        agents.run_agent(
            tmp_path, "hi", output_type=_Payload, max_validation_retries=1
        ),
    )
    assert parsed.value == 1
    assert backend.session_ids == [None, "s1"]


def test_run_agent_structured_output_raises_typed_error_after_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text="not json", session_id="s1"),
            agents.AgentBackendRunResult(text="still not json", session_id="s1"),
        ]
    )

    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )

    with pytest.raises(agents.AgentOutputValidationError) as excinfo:
        agents.run_agent(tmp_path, "hi", output_type=_Payload, max_validation_retries=1)
    err = excinfo.value
    assert err.backend == "sequenced"
    assert err.attempts == 2
    assert err.last_text == "still not json"


def test_run_agent_structured_retry_prompt_truncates_large_validation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )

    parsed = agents.run_agent(
        tmp_path, "hi", output_type=payload_model, max_validation_retries=1
    )
    assert getattr(parsed, "f0") == 1

    retry_prompt = backend.prompts[1]
    assert str(tmp_path) not in retry_prompt

    lines = retry_prompt.splitlines()
    error_index = lines.index("Error:")
    error_line = lines[error_index + 1]
    assert len(error_line) <= 500
    assert error_line.endswith("...")


def test_run_agent_structured_prompts_use_deterministic_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Payload(BaseModel):
        value: int

    backend = _SequencedBackend(
        results=[
            agents.AgentBackendRunResult(text='{"value":1}', session_id="s1"),
        ]
    )

    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )

    parsed = cast(Any, agents.run_agent(tmp_path, "do the thing", output_type=_Payload))
    assert parsed.value == 1

    initial = backend.prompts[0]
    assert initial.startswith("---\n")
    assert "Return exactly one strict JSON value" in initial
    assert "JSON Schema:" in initial
    assert "Task:" in initial
    assert initial.rstrip().endswith("---")


def test_run_agent_validation_error_truncates_last_text_when_huge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    _configure_backend(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        backend_id="sequenced",
        backend_factory=lambda structured_output: backend,
    )

    with pytest.raises(agents.AgentOutputValidationError) as excinfo:
        agents.run_agent(tmp_path, "hi", output_type=_Payload, max_validation_retries=1)
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
