from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "harness"
    / "fitness-functions"
    / "check_dependency_directionality.py"
)


def _write_module(project_root: Path, module_path: str, body: str) -> None:
    path = project_root / "src" / "engineeringagent" / module_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_directionality_fixture(project_root: Path) -> None:
    _write_module(project_root, "cli.py", "")
    _write_module(project_root, "loop.py", "")
    _write_module(project_root, "gates.py", "")
    _write_module(project_root, "validator.py", "from .specs import FeatureSpec\n")
    _write_module(project_root, "specs.py", "")


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


def test_directionality_checker_emits_expected_rule_id(tmp_path: Path) -> None:
    """Emit the stable rule id from the harness command adapter."""
    proc, payload = _run_checker(tmp_path)

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.dep-directionality"


def test_directionality_rule_reports_blocked_import(tmp_path: Path) -> None:
    """Fail when a protected module imports a blocked dependency."""
    _write_directionality_fixture(tmp_path)
    _write_module(tmp_path, "specs.py", "import engineeringagent.loop\n")

    proc, payload = _run_checker(tmp_path)
    violations = payload["violations"]

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        "engineeringagent.specs imports blocked dependency engineeringagent.loop"
        in violation
        for violation in violations
    )


def test_directionality_rule_reports_blocked_loop_runtime_import(
    tmp_path: Path,
) -> None:
    """Fail when protected modules import loop_runtime internals directly."""
    _write_directionality_fixture(tmp_path)
    _write_module(
        tmp_path,
        "validator.py",
        "import engineeringagent.loop_runtime.selection\n",
    )

    proc, payload = _run_checker(tmp_path)
    violations = payload["violations"]

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        (
            "engineeringagent.validator imports blocked dependency "
            "engineeringagent.loop_runtime.selection"
        )
        in violation
        for violation in violations
    )
