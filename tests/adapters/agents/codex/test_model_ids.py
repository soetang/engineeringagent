from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from engineeringagent.adapters.agents.codex import client as client_module
from engineeringagent.adapters.agents.codex.model_ids import normalize_codex_model_id
from engineeringagent.adapters.agents.codex.scaffold import (
    build_codex_scaffold_manifest,
)


def test_normalize_codex_model_id_strips_openai_provider_prefix() -> None:
    assert normalize_codex_model_id("openai/gpt-5.3-codex") == "gpt-5.3-codex"


def test_normalize_codex_model_id_keeps_bare_provider_prefix() -> None:
    assert normalize_codex_model_id("openai/") == "openai/"


def test_runtime_and_scaffold_use_equivalent_model_normalization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    raw_model = "openai/gpt-5.3-codex"

    def _fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        captured["command"] = command
        output_index = command.index("--output-last-message") + 1
        Path(command[output_index]).write_text("payload", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(client_module.subprocess, "run", _fake_subprocess_run)

    client_module.run_codex_exec(
        tmp_path,
        "say hello",
        config=client_module.CodexExecConfig(model=raw_model),
    )
    manifest = build_codex_scaffold_manifest(raw_model)
    normalized = normalize_codex_model_id(raw_model)

    model_index = captured["command"].index("--model") + 1
    assert captured["command"][model_index] == normalized
    assert f'model = "{normalized}"' in manifest[".codex/config.toml"]
