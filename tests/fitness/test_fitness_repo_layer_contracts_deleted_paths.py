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


def test_repo_layer_contracts_rule_blocks_deleted_checks_adapter_directory(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the deleted checks adapter package reappears."""
    legacy_root = tmp_path / "src" / "engineeringagent" / "adapters" / "checks"
    legacy_root.mkdir(parents=True, exist_ok=True)
    (legacy_root / "__init__.py").write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/adapters/checks/__init__.py: deleted legacy module path must remain absent",
        "src/engineeringagent/adapters/checks: deleted legacy directory path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_flat_application_service_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when removed flat application service modules reappear."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "run_loop_service.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/run_loop_service.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_checks_package_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed checks package module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "checks"
        / "service.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/checks/service.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_checks_changed_paths_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed checks changed_paths module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "checks"
        / "changed_paths.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/checks/changed_paths.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_loop_runtime_models_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed loop runtime models module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "loop_runtime"
        / "models.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/loop_runtime/models.py: deleted legacy module path must remain absent"
    ]
