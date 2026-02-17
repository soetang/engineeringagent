from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness-functions"
        / "check_loop_subprocess_boundary.py"
    )


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
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


def test_loop_subprocess_boundary_checker_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit the stable rule id from the harness command adapter."""
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "def run() -> None:\n    return None\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.loop-subprocess-boundary"


def test_loop_subprocess_boundary_rule_reports_multiple_subprocess_patterns(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when multiple non-allowlisted modules invoke subprocess patterns."""
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "\n".join(
            [
                "import subprocess",
                "",
                "def run() -> None:",
                "    subprocess.run(['git', 'status'], check=False)",
            ]
        ),
    )
    _write_module(
        tmp_path,
        "src/engineeringagent/process_runner.py",
        "\n".join(
            [
                "import subprocess as sp",
                "",
                "def run_process() -> None:",
                "    sp.run(['git', 'status'], check=False)",
            ]
        ),
    )
    _write_module(
        tmp_path,
        "src/engineeringagent/from_import_runner.py",
        "\n".join(
            [
                "from subprocess import run as run_cmd",
                "",
                "def run() -> None:",
                "    run_cmd(['git', 'status'], check=False)",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = payload["violations"]

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        "src/engineeringagent/loop.py:4 uses subprocess.run" in violation
        for violation in violations
    )
    assert any(
        "src/engineeringagent/process_runner.py:4 uses sp.run" in violation
        for violation in violations
    )
    assert any(
        "src/engineeringagent/from_import_runner.py:4 uses run_cmd(...) from subprocess"
        in violation
        for violation in violations
    )


def test_loop_subprocess_boundary_rule_allows_approved_command_boundary_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when subprocess calls stay inside explicit allowlisted modules."""
    _write_module(
        tmp_path,
        "src/engineeringagent/gates.py",
        "\n".join(
            [
                "import subprocess",
                "",
                "def run_gate() -> None:",
                "    subprocess.run(['git', 'status'], check=False)",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []
