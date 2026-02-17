from __future__ import annotations

import sys
from pathlib import Path


if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


def test_repo_engineeringagent_toml_enables_opencode_toggles() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "engineeringagent.toml"
    assert config_path.exists(), "expected engineeringagent.toml at repo root"

    document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    harness = document.get("harness")
    assert isinstance(harness, dict)

    fitness = harness.get("fitness")
    assert isinstance(fitness, dict)
    assert fitness.get("opencode-real-smoke") is True

    pytest_table = harness.get("pytest")
    assert isinstance(pytest_table, dict)
    assert pytest_table.get("opencode-integration") is True
