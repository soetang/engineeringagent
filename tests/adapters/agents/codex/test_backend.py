from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from engineeringagent.adapters.agents import (
    AgentBackendError,
    AgentOutputValidationError,
)
from engineeringagent.adapters.agents.codex import CodexAgentBackend
from engineeringagent.adapters.agents.codex import backend as backend_module
from engineeringagent.adapters.agents.codex import client as client_module
from engineeringagent.ports import AgentRunRequest


def _complete_with_output(
    command: Any,
    *,
    payload: str = "payload",
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    args: Any | None = None,
) -> subprocess.CompletedProcess[str]:
    output_index = command.index("--output-last-message") + 1
    Path(command[output_index]).write_text(payload, encoding="utf-8")
    process_args = command if args is None else args
    return subprocess.CompletedProcess(
        process_args,
        returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_codex_exec_text_mode_uses_output_last_message_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _complete_with_output(
            command,
            payload="final payload",
            stdout="progress",
        )

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    result = client_module.run_codex_exec(tmp_path, "say hello")

    assert result.output_last_message == "final payload"
    assert result.stdout == "progress"
    assert captured["command"][0:4] == ["codex", "exec", "--sandbox", "workspace-write"]
    assert "--output-schema" not in captured["command"]
    assert captured["command"][-1] == "say hello"
    assert captured["kwargs"]["cwd"] == tmp_path


def test_codex_exec_structured_mode_writes_schema_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        captured["command"] = command
        schema_index = command.index("--output-schema") + 1
        captured["schema_text"] = Path(command[schema_index]).read_text(
            encoding="utf-8"
        )
        return _complete_with_output(command, payload='{"ok":true}')

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    result = client_module.run_codex_exec(
        tmp_path,
        "return json",
        config=client_module.CodexExecConfig(
            output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}}
        ),
    )

    assert result.output_last_message == '{"ok":true}'
    assert "--output-schema" in captured["command"]
    assert '"ok"' in captured["schema_text"]


def test_codex_exec_keeps_hyphen_prefixed_prompt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        captured["command"] = command
        return _complete_with_output(command, payload="ok")

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    client_module.run_codex_exec(tmp_path, "--- reviewer payload")
    assert captured["command"][-1] == "--- reviewer payload"


def test_codex_exec_returns_empty_payload_when_output_file_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(command, 0, stdout="progress", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    result = client_module.run_codex_exec(tmp_path, "say hello")
    assert result.output_last_message == ""


def test_codex_exec_includes_profile_and_model_flags(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        del kwargs
        return _complete_with_output(command)

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    client_module.run_codex_exec(
        tmp_path,
        "say hello",
        config=client_module.CodexExecConfig(profile="p1", model="m1"),
    )

    assert "--profile" in captured["command"]
    assert "p1" in captured["command"]
    assert "--model" in captured["command"]
    assert "m1" in captured["command"]


def test_codex_exec_strips_openai_provider_prefix_from_model_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        del kwargs
        return _complete_with_output(command)

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    client_module.run_codex_exec(
        tmp_path,
        "say hello",
        config=client_module.CodexExecConfig(model="openai/gpt-5.3-codex"),
    )

    model_index = captured["command"].index("--model") + 1
    assert captured["command"][model_index] == "gpt-5.3-codex"


def test_codex_exec_normalizes_tuple_process_args(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        return _complete_with_output(command, args=tuple(command))

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    result = client_module.run_codex_exec(tmp_path, "say hello")

    assert result.args[0:5] == [
        "codex",
        "exec",
        "--sandbox",
        "workspace-write",
        "--output-last-message",
    ]
    assert result.args[-1] == "say hello"
    assert len(result.args) == 7


def test_codex_exec_normalizes_scalar_process_args(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        return _complete_with_output(command, args="codex exec")

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    result = client_module.run_codex_exec(tmp_path, "say hello")

    assert result.args == ["codex exec"]


def test_codex_backend_run_structured_emits_nested_required_fields_in_output_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Nested(BaseModel):
        child: str

    class _Item(BaseModel):
        list_item: int

    class _Payload(BaseModel):
        root: str
        nested: _Nested
        items: list[_Item]

    captured: dict[str, Any] = {}

    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **kwargs: Any,
    ) -> client_module.CodexExecResult:
        captured["config"] = kwargs["config"]
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=0,
            stdout="",
            stderr="",
            output_last_message='{"root":"ok","nested":{"child":"v"},"items":[{"list_item":1}]}',
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    payload = backend.run_structured(
        tmp_path,
        "return json",
        output_type=_Payload,
        max_validation_retries=2,
    )

    assert payload.root == "ok"
    schema = captured["config"].output_schema
    assert schema is not None
    assert schema["required"] == ["root", "nested", "items"]
    defs = schema["$defs"]
    object_defs = [
        definition
        for definition in defs.values()
        if isinstance(definition, dict)
        and definition.get("type") == "object"
        and isinstance(definition.get("properties"), dict)
    ]
    assert object_defs
    for definition in object_defs:
        properties = definition["properties"]
        assert set(definition["required"]) == set(properties)


def test_codex_backend_run_structured_normalizes_nonstandard_schema_nodes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        model_config = ConfigDict(
            json_schema_extra={
                "if": {
                    "type": "object",
                    "properties": {"conditional": {"type": "boolean"}},
                }
            }
        )

        root: str

    captured: dict[str, Any] = {}

    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **kwargs: Any,
    ) -> client_module.CodexExecResult:
        captured["config"] = kwargs["config"]
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=0,
            stdout="",
            stderr="",
            output_last_message='{"root":"ok"}',
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    payload = backend.run_structured(
        tmp_path,
        "return json",
        output_type=_Payload,
        max_validation_retries=1,
    )

    assert payload.root == "ok"
    schema = captured["config"].output_schema
    assert schema is not None
    assert schema["required"] == ["root"]
    assert schema["if"]["required"] == ["conditional"]


def test_codex_backend_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_run_codex_exec(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> client_module.CodexExecResult:
        captured["project_root"] = project_root
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return client_module.CodexExecResult(
            args=["codex", "exec"],
            returncode=0,
            stdout="progress",
            stderr="",
            output_last_message="final payload",
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend(profile="p1", model="m1")
    result = backend.run(tmp_path, "say hello")

    assert backend.name == "codex"
    assert result.text == "final payload"
    assert result.session_id is None
    assert captured["project_root"] == tmp_path
    assert captured["prompt"] == "say hello"
    config = captured["kwargs"]["config"]
    assert isinstance(config, client_module.CodexExecConfig)
    assert config.profile == "p1"
    assert config.model == "m1"
    assert config.sandbox == "workspace-write"
    assert config.output_schema is None


def test_codex_backend_run_request_text_returns_text_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_run_codex_exec(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> client_module.CodexExecResult:
        captured["project_root"] = project_root
        captured["prompt"] = prompt
        captured["config"] = kwargs["config"]
        return client_module.CodexExecResult(
            args=["codex", "exec", prompt],
            returncode=0,
            stdout="progress",
            stderr="",
            output_last_message="plain text",
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend(profile="p1", model="m1")
    result = backend.run_request(
        AgentRunRequest(project_root=tmp_path, prompt="say hello", output_type=str)
    )

    assert result == "plain text"
    assert captured["project_root"] == tmp_path
    assert captured["prompt"] == "say hello"
    assert captured["config"].output_schema is None


def test_codex_backend_run_request_structured_returns_parsed_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        ok: bool

    captured: dict[str, Any] = {}

    def _fake_run_codex_exec(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> client_module.CodexExecResult:
        captured["project_root"] = project_root
        captured["prompt"] = prompt
        captured["config"] = kwargs["config"]
        return client_module.CodexExecResult(
            args=["codex", "exec", prompt],
            returncode=0,
            stdout="progress",
            stderr="",
            output_last_message='{"ok": true}',
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend(profile="p1", model="m1")
    payload = backend.run_request(
        AgentRunRequest(
            project_root=tmp_path,
            prompt="return json",
            output_type=_Payload,
            max_validation_retries=9,
        )
    )

    assert payload.ok is True
    assert captured["project_root"] == tmp_path
    assert captured["prompt"] == "return json"
    assert captured["config"].output_schema is not None


def test_codex_backend_reads_profile_model_from_repo_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents.codex]\nprofile = "repo-profile"\nmodel = "repo-model"\n',
        encoding="utf-8",
    )

    def _fake_run_codex_exec(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> client_module.CodexExecResult:
        captured["project_root"] = project_root
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return client_module.CodexExecResult(
            args=["codex", "exec"],
            returncode=0,
            stdout="",
            stderr="",
            output_last_message="ok",
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    backend.run(tmp_path, "say hello")

    assert captured["project_root"] == tmp_path
    assert captured["prompt"] == "say hello"
    config = captured["kwargs"]["config"]
    assert config.profile == "repo-profile"
    assert config.model == "repo-model"


def test_codex_backend_raises_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **_kwargs: Any,
    ) -> client_module.CodexExecResult:
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=13,
            stdout="some stdout",
            stderr="some stderr",
            output_last_message="",
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    with pytest.raises(AgentBackendError, match=r"codex exec failed") as exc_info:
        backend.run(tmp_path, "p")

    exc = exc_info.value
    assert exc.backend == "codex"
    assert exc.returncode == 13
    assert exc.stdout == "some stdout"
    assert exc.stderr == "some stderr"
    assert exc.command_args == ["codex", "exec", "prompt"]


def test_codex_backend_maps_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **_kwargs: Any,
    ) -> client_module.CodexExecResult:
        raise FileNotFoundError("No such file or directory: codex")

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    with pytest.raises(
        AgentBackendError, match=r"codex executable missing"
    ) as exc_info:
        backend.run(tmp_path, "p")

    assert exc_info.value.backend == "codex"


def test_codex_backend_run_structured_uses_schema_and_validates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        ok: bool

    captured: dict[str, Any] = {}

    def _fake_run_codex_exec(
        project_root: Path,
        prompt: str,
        **kwargs: Any,
    ) -> client_module.CodexExecResult:
        captured["project_root"] = project_root
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=0,
            stdout="progress output",
            stderr="",
            output_last_message=json.dumps({"ok": True}),
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend(profile="p1", model="m1")
    parsed = backend.run_structured(
        tmp_path,
        "return json",
        output_type=_Payload,
        max_validation_retries=3,
    )

    assert parsed.ok is True
    config = captured["kwargs"]["config"]
    assert config.profile == "p1"
    assert config.model == "m1"
    assert config.sandbox == "workspace-write"
    assert config.output_schema is not None
    assert config.output_schema["type"] == "object"
    assert config.output_schema["properties"]["ok"]["type"] == "boolean"


def test_codex_backend_run_structured_raises_validation_error_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        model_config = ConfigDict(extra="forbid")

        ok: bool

    calls = 0

    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **_kwargs: Any,
    ) -> client_module.CodexExecResult:
        nonlocal calls
        calls += 1
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=0,
            stdout="progress output",
            stderr="",
            output_last_message='{"ok":true,"extra":1}',
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    with pytest.raises(AgentOutputValidationError) as exc_info:
        backend.run_structured(
            tmp_path,
            "return json",
            output_type=_Payload,
            max_validation_retries=5,
        )

    assert calls == 1
    assert exc_info.value.backend == "codex"
    assert exc_info.value.attempts == 1


def test_codex_backend_run_structured_parse_error_has_stable_public_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        ok: bool

    calls = 0

    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **_kwargs: Any,
    ) -> client_module.CodexExecResult:
        nonlocal calls
        calls += 1
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=0,
            stdout="",
            stderr="",
            output_last_message="not-json",
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    with pytest.raises(AgentOutputValidationError) as exc_info:
        backend.run_structured(
            tmp_path,
            "return json",
            output_type=_Payload,
            max_validation_retries=9,
        )

    assert calls == 1
    assert exc_info.value.backend == "codex"
    assert exc_info.value.attempts == 1
    assert exc_info.value.last_text == "not-json"
    assert exc_info.value.error_summary


def test_codex_backend_run_structured_uses_output_last_message_as_canonical_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        ok: bool

    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **_kwargs: Any,
    ) -> client_module.CodexExecResult:
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=0,
            stdout='{"ok": false}',
            stderr="",
            output_last_message='{"ok": true}',
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    payload = backend.run_structured(
        tmp_path,
        "return json",
        output_type=_Payload,
        max_validation_retries=2,
    )

    assert payload.ok is True


def test_codex_backend_run_structured_passes_enum_and_no_extra_schema_constraints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        model_config = ConfigDict(extra="forbid")

        mode: Literal["review", "fix"]

    captured: dict[str, Any] = {}

    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **kwargs: Any,
    ) -> client_module.CodexExecResult:
        captured["config"] = kwargs["config"]
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=0,
            stdout="",
            stderr="",
            output_last_message='{"mode":"review"}',
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    payload = backend.run_structured(
        tmp_path,
        "return json",
        output_type=_Payload,
        max_validation_retries=0,
    )

    assert payload.mode == "review"
    schema = captured["config"].output_schema
    assert schema is not None
    assert schema["additionalProperties"] is False
    assert schema["properties"]["mode"]["enum"] == ["review", "fix"]


def test_codex_backend_run_structured_promotes_optional_fields_to_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        value: int
        required_actions: list[str] = Field(default_factory=list)
        scope_notes: str | None = None

    captured: dict[str, Any] = {}

    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **kwargs: Any,
    ) -> client_module.CodexExecResult:
        captured["config"] = kwargs["config"]
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=0,
            stdout="",
            stderr="",
            output_last_message='{"value":1,"required_actions":[],"scope_notes":null}',
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    payload = backend.run_structured(
        tmp_path,
        "return json",
        output_type=_Payload,
        max_validation_retries=0,
    )

    assert payload.value == 1
    schema = captured["config"].output_schema
    assert schema is not None
    assert schema["required"] == ["value", "required_actions", "scope_notes"]


def test_codex_backend_run_structured_truncates_huge_invalid_payload_in_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _Payload(BaseModel):
        value: int

    huge_invalid_payload = "x" * 4000

    def _fake_run_codex_exec(
        _project_root: Path,
        _prompt: str,
        **_kwargs: Any,
    ) -> client_module.CodexExecResult:
        return client_module.CodexExecResult(
            args=["codex", "exec", "prompt"],
            returncode=0,
            stdout="",
            stderr="",
            output_last_message=huge_invalid_payload,
        )

    monkeypatch.setattr(backend_module, "run_codex_exec", _fake_run_codex_exec)

    backend = CodexAgentBackend()
    with pytest.raises(AgentOutputValidationError) as exc_info:
        backend.run_structured(
            tmp_path,
            "return json",
            output_type=_Payload,
            max_validation_retries=3,
        )

    assert exc_info.value.last_text is not None
    assert len(exc_info.value.last_text) <= 2000
    assert exc_info.value.last_text.endswith("...")
