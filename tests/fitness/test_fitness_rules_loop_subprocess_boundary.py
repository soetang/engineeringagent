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


def test_loop_subprocess_boundary_rule_reports_expected_violations_and_respects_allowlist(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Report expected violations in one semgrep run.

    This test writes multiple source modules into a single tmp fixture so the checker
    pays semgrep startup cost once.
    """
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

    # Backend command execution is intentionally centralized behind allowlisted
    # client adapter modules.
    _write_module(
        tmp_path,
        "src/engineeringagent/agents/backends/opencode/client.py",
        "\n".join(
            [
                "import subprocess",
                "",
                "def run_agent() -> None:",
                "    subprocess.run(['opencode', '--version'], check=False)",
            ]
        ),
    )
    _write_module(
        tmp_path,
        "src/engineeringagent/agents/backends/codex/client.py",
        "\n".join(
            [
                "import subprocess",
                "",
                "def run_agent() -> None:",
                "    subprocess.run(['codex', '--version'], check=False)",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = payload["violations"]

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.loop-subprocess-boundary"
    assert payload["status"] == "fail"
    assert isinstance(violations, list)
    assert len(violations) == 3
    assert violations == sorted(violations)
    assert all(
        "src/engineeringagent/gates.py:" not in violation for violation in violations
    )

    expected = [
        ("src/engineeringagent/loop.py", ("subprocess.run",)),
        ("src/engineeringagent/process_runner.py", ("sp.run",)),
        ("src/engineeringagent/from_import_runner.py", ("from subprocess", "run_cmd")),
    ]
    for file_path, patterns in expected:
        match = next((v for v in violations if file_path in v), None)
        assert match is not None, f"Missing violation for {file_path}: {violations}"
        assert any(p in match for p in patterns), (
            f"Violation for {file_path} missing expected pattern {patterns}: {match}"
        )
