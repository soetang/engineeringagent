from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_repo_layer_contracts.py"
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


def test_repo_layer_contracts_rule_blocks_runtime_execution_loop_import(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when bootstrap runtime execution reaches back into the loop facade."""
    bootstrap_root = tmp_path / "src" / "engineeringagent" / "bootstrap"
    bootstrap_root.mkdir(parents=True, exist_ok=True)
    (bootstrap_root / "runtime_execution.py").write_text(
        "import engineeringagent.loop\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/bootstrap/runtime_execution.py: bootstrap runtime execution must not import the legacy engineeringagent.loop facade; use engineeringagent.bootstrap.runtime_support and engineeringagent.loop_runtime modules directly"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_legacy_directory_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when a deleted legacy package directory reappears."""
    legacy_root = tmp_path / "src" / "engineeringagent" / "application" / "contracts"
    legacy_root.mkdir(parents=True, exist_ok=True)
    (legacy_root / "__pycache__").mkdir()

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/contracts: deleted legacy directory path must remain absent"
    ]
