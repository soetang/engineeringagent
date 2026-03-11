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
        / "check_legacy_run_loop_bridge_absent.py"
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


def test_legacy_run_loop_bridge_absent_rule_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit the stable rule id for removed run-loop bridge paths."""
    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.legacy-run-loop-bridge-absent"


def test_legacy_run_loop_bridge_absent_rule_passes_when_paths_are_absent(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when the deleted legacy bridge module name stays absent."""
    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_legacy_run_loop_bridge_absent_rule_fails_when_paths_return(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the deleted loop adapter package reappears."""
    adapter_path = tmp_path / "src" / "engineeringagent" / "adapters" / "loop"
    adapter_path.mkdir(parents=True, exist_ok=True)
    (adapter_path / "__init__.py").write_text("", encoding="utf-8")
    (adapter_path / "legacy_run_loop_executor.py").write_text("", encoding="utf-8")
    (adapter_path / "runtime_feature_iteration_executor.py").write_text(
        "", encoding="utf-8"
    )
    (adapter_path / "runtime_run_loop_executor.py").write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "src/engineeringagent/adapters/loop/__init__.py: deleted legacy run-loop bridge path must remain absent; "
        "keep runtime loop execution wiring under engineeringagent.bootstrap.runtime_execution and do not restore the deleted engineeringagent.adapters.loop package.",
        "src/engineeringagent/adapters/loop/runtime_feature_iteration_executor.py: deleted legacy run-loop bridge path must remain absent; "
        "keep runtime loop execution wiring under engineeringagent.bootstrap.runtime_execution and do not restore the deleted engineeringagent.adapters.loop package.",
        "src/engineeringagent/adapters/loop/legacy_run_loop_executor.py: deleted legacy run-loop bridge path must remain absent; "
        "keep runtime loop execution wiring under engineeringagent.bootstrap.runtime_execution and do not restore the deleted engineeringagent.adapters.loop package.",
        "src/engineeringagent/adapters/loop/runtime_run_loop_executor.py: deleted legacy run-loop bridge path must remain absent; "
        "keep runtime loop execution wiring under engineeringagent.bootstrap.runtime_execution and do not restore the deleted engineeringagent.adapters.loop package.",
    ]
