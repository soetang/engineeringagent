from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import yaml


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
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
    *,
    checker_path: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def test_detects_forbidden_uvx_from_dot_in_feature_verification(
    tmp_path: Path,
    repo_root: Path,
) -> None:
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

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert (
        "docs/spec/features/FEAT-001.yaml:subtasks[0].verification[0]" in violations[0]
    )


def test_detects_forbidden_uvx_from_dot_in_checks_config(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when a command check uses uvx --from . engineeringagent."""
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
        tmp_path / "harness/checks.yaml",
        {
            "contract_version": "1.0",
            "checks": {
                "fitness_validate": {
                    "type": "command",
                    "command": "uvx --from . engineeringagent checks run --checks fitness --phase iteration_end",
                }
            },
        },
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "harness/checks.yaml:checks.fitness_validate.command" in violations[0]


def test_allows_uv_run_source_first_forms(tmp_path: Path, repo_root: Path) -> None:
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
                        ".venv/bin/engineeringagent run --all --dry-run",
                    ],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / "harness/checks.yaml",
        {
            "contract_version": "1.0",
            "checks": {
                "spec_validate": {
                    "type": "command",
                    "command": "uv run python -m engineeringagent.cli validate",
                },
                "fitness_validate": {
                    "type": "command",
                    "command": "uv run engineeringagent checks run --checks fitness --phase iteration_end",
                },
            },
        },
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_repo_scoped_commands_are_policy_compliant(repo_root: Path) -> None:
    """Pass when repository-scoped loop commands avoid uvx --from . self-invocation."""
    proc, payload = _run_checker(repo_root, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []
