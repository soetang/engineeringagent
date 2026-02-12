from __future__ import annotations

from pathlib import Path

import yaml

from engineeringagent.gates import list_profiles, load_gate_config


def test_load_gate_config_scaffolds_missing_gates_file(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"

    config = load_gate_config(gates_path)

    assert gates_path.exists()
    assert list_profiles(config) == ["loop_fast", "precommit"]


def test_scaffolded_gates_config_has_expected_commands(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"

    load_gate_config(gates_path)
    config = yaml.safe_load(gates_path.read_text(encoding="utf-8"))

    assert (
        config["gates"]["ruff_validate"]["run"]
        == "uv run ruff check src/engineeringagent"
    )
    assert config["gates"]["pytest_validate"]["run"] == "uv run pytest -q"
    assert "precommit" in config["profiles"]
    assert "loop_fast" in config["profiles"]
