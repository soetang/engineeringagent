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
        / "check_presentation_cli_module_locations.py"
    )


def _write_file(project_root: Path, relative_path: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


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


def test_rule_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit the stable rule id for init CLI support locality."""
    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["rule_id"] == "architecture.init-cli-support-location"


def test_rule_passes_for_target_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when init CLI support lives under bootstrap."""
    _write_file(tmp_path, "src/engineeringagent/bootstrap/init_cli_support.py")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_rule_fails_for_legacy_root_init_cli_support_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the deleted root-level init CLI helper returns."""
    _write_file(tmp_path, "src/engineeringagent/bootstrap/init_cli_support.py")
    _write_file(tmp_path, "src/engineeringagent/init_cli_support.py")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "src/engineeringagent/init_cli_support.py: legacy init CLI support module path is not allowed; "
        "keep init CLI support wiring under engineeringagent.bootstrap; "
        "do not restore the root-level engineeringagent.init_cli_support module."
    ]
