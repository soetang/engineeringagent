from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import yaml


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "harness"
    / "fitness-functions"
    / "check_source_first_loop_commands.py"
)


def _write_yaml(path: Path, content: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(content, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def _run_checker(
    project_root: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def test_detects_forbidden_uvx_from_dot_in_feature_verification(tmp_path: Path) -> None:
    """Fail when a feature subtask verification command uses uvx --from ."""
    _write_yaml(
        tmp_path / "docs/spec/features/FEAT-001.yaml",
        {
            "id": "FEAT-001",
            "subtasks": [
                {
                    "id": "ST-001",
                    "verification": ["uvx --from . engineeringagent validate"],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / "harness/gates.yaml",
        {
            "gates": {
                "spec_validate": {
                    "run": "uv run python -m engineeringagent.cli validate"
                }
            }
        },
    )

    proc, payload = _run_checker(tmp_path)

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert (
        "docs/spec/features/FEAT-001.yaml:subtasks[0].verification[0]" in violations[0]
    )


def test_detects_forbidden_uvx_from_dot_in_gates_config(tmp_path: Path) -> None:
    """Fail when a gate command uses uvx --from . engineeringagent."""
    _write_yaml(
        tmp_path / "docs/spec/features/FEAT-001.yaml",
        {
            "id": "FEAT-001",
            "subtasks": [
                {
                    "id": "ST-001",
                    "verification": ["uv run python -m engineeringagent.cli validate"],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / "harness/gates.yaml",
        {
            "gates": {
                "fitness_validate": {
                    "run": "uvx --from . engineeringagent fitness run --format json"
                }
            }
        },
    )

    proc, payload = _run_checker(tmp_path)

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "harness/gates.yaml:gates.fitness_validate.run" in violations[0]


def test_allows_uv_run_source_first_forms(tmp_path: Path) -> None:
    """Pass when scoped commands use uv run or direct local workspace execution."""
    _write_yaml(
        tmp_path / "docs/spec/features/FEAT-001.yaml",
        {
            "id": "FEAT-001",
            "subtasks": [
                {
                    "id": "ST-001",
                    "verification": [
                        "uv run python -m engineeringagent.cli validate",
                        ".venv/bin/engineeringagent gates run --profile loop_fast",
                    ],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / "harness/gates.yaml",
        {
            "gates": {
                "spec_validate": {
                    "runner": {
                        "type": "command",
                        "command": "uv run python -m engineeringagent.cli validate",
                    }
                },
                "fitness_validate": {
                    "run": "uv run python -m engineeringagent.cli fitness run --format json"
                },
            }
        },
    )

    proc, payload = _run_checker(tmp_path)

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_repo_scoped_commands_are_policy_compliant() -> None:
    """Pass when repository-scoped loop commands avoid uvx --from . self-invocation."""
    project_root = Path(__file__).resolve().parents[1]

    proc, payload = _run_checker(project_root)

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []
