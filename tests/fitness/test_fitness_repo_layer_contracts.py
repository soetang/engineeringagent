from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


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


def test_repo_layer_contracts_rule_blocks_bootstrap_runtime_executor_classes(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when bootstrap runtime execution owns concrete executor classes."""
    bootstrap_root = tmp_path / "src" / "engineeringagent" / "bootstrap"
    bootstrap_root.mkdir(parents=True, exist_ok=True)
    (bootstrap_root / "runtime_execution.py").write_text(
        "class RuntimeRunLoopExecutor:\n    pass\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/bootstrap/runtime_execution.py: bootstrap runtime execution must not declare RuntimeRunLoopExecutor; move runtime executor implementations under engineeringagent.adapters.runtime"
    ]


def test_repo_layer_contracts_rule_blocks_runtime_support_loop_import(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when bootstrap runtime support reaches back into the loop facade."""
    bootstrap_root = tmp_path / "src" / "engineeringagent" / "bootstrap"
    bootstrap_root.mkdir(parents=True, exist_ok=True)
    (bootstrap_root / "runtime_support.py").write_text(
        "import engineeringagent.loop\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/bootstrap/runtime_support.py: bootstrap runtime support must not import the legacy engineeringagent.loop facade; call the canonical engineeringagent.agents boundary directly"
    ]


def test_repo_layer_contracts_rule_allows_loop_runtime_models_bridge(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the loop-runtime import of audit-domain iteration models."""
    loop_runtime_root = tmp_path / "src" / "engineeringagent" / "loop_runtime"
    loop_runtime_root.mkdir(parents=True, exist_ok=True)
    (loop_runtime_root / "iteration.py").write_text(
        "from engineeringagent.domain.audit import IterationReport\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_repo_layer_contracts_rule_allows_quality_runtime_bridge(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the quality runtime adapter to compose checks internals."""
    runtime_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "adapters"
        / "quality"
        / "runtime.py"
    )
    runtime_module.parent.mkdir(parents=True, exist_ok=True)
    runtime_module.write_text(
        "\n".join(
            [
                "from engineeringagent.checks.config_selection import load_selected_harness_checks_document",
                "from engineeringagent.checks.strategies import CommandCheckStrategy",
                "",
                "__all__ = ['load_selected_harness_checks_document', 'CommandCheckStrategy']",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_repo_layer_contracts_rule_blocks_deleted_application_checks_runtime(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed application checks runtime module reappears."""
    legacy_runtime = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "checks"
        / "runtime.py"
    )
    legacy_runtime.parent.mkdir(parents=True, exist_ok=True)
    legacy_runtime.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/checks/runtime.py: deleted legacy module path must remain absent",
        "src/engineeringagent/application/checks: deleted legacy directory path must remain absent",
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
