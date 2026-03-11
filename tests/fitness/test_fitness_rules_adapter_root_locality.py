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
        / "check_adapter_root_locality.py"
    )


def _write_module(project_root: Path, module_path: str, body: str = "") -> None:
    path = project_root / module_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


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


def test_adapter_root_locality_checker_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit the stable rule id from the harness command adapter."""
    _write_module(tmp_path, "src/engineeringagent/adapters/__init__.py")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.adapter-root-locality"


def test_adapter_root_locality_rule_reports_root_level_adapter_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when adapter implementations are placed at the adapters package root."""
    _write_module(tmp_path, "src/engineeringagent/adapters/__init__.py")
    _write_module(tmp_path, "src/engineeringagent/adapters/run_loop_executor.py")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "src/engineeringagent/adapters/run_loop_executor.py: root-level adapter module is not allowed; "
        "move root-level adapter implementation files into a focused subpackage under "
        "engineeringagent.adapters/."
    ]


def test_adapter_root_locality_rule_allows_subpackage_localized_adapters(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow adapter implementations that live under focused adapter subpackages."""
    _write_module(tmp_path, "src/engineeringagent/adapters/__init__.py")
    _write_module(tmp_path, "src/engineeringagent/adapters/progress/__init__.py")
    _write_module(
        tmp_path,
        "src/engineeringagent/adapters/progress/filesystem_journal.py",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []
