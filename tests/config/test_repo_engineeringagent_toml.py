from __future__ import annotations

import sys
from pathlib import Path

from engineeringagent.config import resolve_agents_backend_id


if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


def test_repo_engineeringagent_toml_enables_opencode_toggles() -> None:
    """Assert repo-level TOML defaults include expected feature toggles."""
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "engineeringagent.toml"
    assert config_path.exists(), "expected engineeringagent.toml at repo root"

    document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    harness = document.get("harness")
    assert isinstance(harness, dict)

    fitness = harness.get("fitness")
    assert isinstance(fitness, dict)
    assert fitness.get("opencode-real-smoke") is False

    pytest_table = harness.get("pytest")
    assert isinstance(pytest_table, dict)
    assert pytest_table.get("opencode-integration") is True


def test_repo_engineeringagent_toml_sets_codex_as_default_agent_backend() -> None:
    """Assert repository-level backend selection defaults to codex."""
    repo_root = Path(__file__).resolve().parents[2]

    assert resolve_agents_backend_id(repo_root) == "codex"


def test_repo_includes_codex_profile_config_for_default_backend() -> None:
    """Assert repo codex profile config exists for deterministic backend execution."""
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / ".codex" / "config.toml"

    assert config_path.exists(), "expected .codex/config.toml at repo root"

    document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    profiles = document.get("profiles")
    assert isinstance(profiles, dict)

    engineeringagent = profiles.get("engineeringagent")
    assert isinstance(engineeringagent, dict)
    assert engineeringagent.get("sandbox_mode") == "workspace-write"
    assert engineeringagent.get("approval_policy") == "never"
    assert engineeringagent.get("model"), "codex profile model must be configured"
