from __future__ import annotations

from engineeringagent.adapters.agents.codex.model_ids import normalize_codex_model_id
from engineeringagent.adapters.agents.codex.scaffold import (
    build_codex_scaffold_manifest,
)


def test_build_codex_scaffold_manifest_renders_model() -> None:
    manifest = build_codex_scaffold_manifest("openai/gpt-5.3-codex-spark")

    assert ".codex/config.toml" in manifest
    assert 'model = "gpt-5.3-codex-spark"' in manifest[".codex/config.toml"]
    assert 'approval_policy = "never"' in manifest[".codex/config.toml"]


def test_normalize_codex_model_id_keeps_bare_provider_prefix() -> None:
    assert normalize_codex_model_id("openai/") == "openai/"
