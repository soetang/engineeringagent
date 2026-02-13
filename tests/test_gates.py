from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest
import yaml

from engineeringagent.cli import cmd_gates_run
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


def test_empty_profile_returns_friendly_success_message(
    tmp_path: Path, capsys: Any
) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {
                    "precommit": [],
                },
                "gates": {},
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    code = cmd_gates_run(Namespace(project_root=str(tmp_path), profile="precommit"))
    output = capsys.readouterr().out

    assert code == 0
    assert "gates profile has no configured gates: precommit" in output


def test_load_gate_config_rejects_invalid_contract(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {
                    "precommit": ["yaml_validate"],
                },
                "gates": {
                    "yaml_validate": {
                        "run": 123,
                        "extra": True,
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        load_gate_config(gates_path)

    message = str(excinfo.value)
    assert "invalid gates config" in message
    assert "gates.yaml:gates.yaml_validate.extra" in message
    assert "gates.yaml:gates.yaml_validate.run" in message


def test_commit_msg_hook_configuration() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_text = (repo_root / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "engineeringagent-commit-msg" in config_text
    assert "validate_commit_messages.py --commit-msg-file" in config_text
    assert "stages: [commit-msg]" in config_text


def test_commit_message_ci_gate_registered() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    workflow_text = (repo_root / ".github" / "workflows" / "ci.yaml").read_text(
        encoding="utf-8"
    )

    assert "Validate commit subjects" in workflow_text
    assert "validate_commit_messages.py --commit-range" in workflow_text
