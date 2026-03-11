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
        / "check_loop_subprocess_boundary.py"
    )


def _policy_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "policies"
        / "loop_subprocess_boundary_policy.yaml"
    )


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
    config_file: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    command = [sys.executable, str(checker_path)]
    if config_file is not None:
        command.extend(["--config-file", str(config_file)])

    proc = subprocess.run(
        command,
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
    """Report expected violations in one native checker run.

    This test writes multiple source modules into a single tmp fixture so the checker
    scans once.
    """
    modules = [
        (
            "src/engineeringagent/loop.py",
            "\n".join(
                [
                    "import subprocess",
                    "",
                    "def run() -> None:",
                    "    subprocess.run(['git', 'status'], check=False)",
                ]
            ),
        ),
        (
            "src/engineeringagent/process_runner.py",
            "\n".join(
                [
                    "import subprocess as sp",
                    "",
                    "def run_process() -> None:",
                    "    sp.run(['git', 'status'], check=False)",
                ]
            ),
        ),
        (
            "src/engineeringagent/from_import_runner.py",
            "\n".join(
                [
                    "from subprocess import run as run_cmd",
                    "",
                    "def run() -> None:",
                    "    run_cmd(['git', 'status'], check=False)",
                ]
            ),
        ),
        (
            "src/engineeringagent/wildcard_import_runner.py",
            "\n".join(
                [
                    "from subprocess import *",
                    "",
                    "def run() -> None:",
                    "    check_output(['git', 'status'])",
                ]
            ),
        ),
        (
            "src/engineeringagent/from_import_check_call_runner.py",
            "\n".join(
                [
                    "from subprocess import check_call as call_check",
                    "",
                    "def run() -> None:",
                    "    call_check(['git', 'status'])",
                ]
            ),
        ),
        # Backend command execution is intentionally centralized behind allowlisted
        # client adapter modules.
        (
            "src/engineeringagent/agents/backends/opencode/client.py",
            "\n".join(
                [
                    "import subprocess",
                    "",
                    "def run_agent() -> None:",
                    "    subprocess.run(['opencode', '--version'], check=False)",
                ]
            ),
        ),
        (
            "src/engineeringagent/agents/backends/codex/client.py",
            "\n".join(
                [
                    "import subprocess",
                    "",
                    "def run_agent() -> None:",
                    "    subprocess.run(['codex', '--version'], check=False)",
                ]
            ),
        ),
    ]
    for relative_path, body in modules:
        _write_module(tmp_path, relative_path, body)

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )
    violations = payload["violations"]

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.loop-subprocess-boundary"
    assert payload["status"] == "fail"
    assert isinstance(violations, list)
    assert len(violations) == 5
    assert violations == sorted(violations)

    expected = [
        ("src/engineeringagent/loop.py", ("subprocess.run",)),
        ("src/engineeringagent/process_runner.py", ("sp.run",)),
        ("src/engineeringagent/from_import_runner.py", ("from subprocess", "run_cmd")),
        (
            "src/engineeringagent/wildcard_import_runner.py",
            ("from subprocess", "check_output"),
        ),
        (
            "src/engineeringagent/from_import_check_call_runner.py",
            ("from subprocess", "call_check"),
        ),
    ]
    for file_path, patterns in expected:
        match = next((v for v in violations if file_path in v), None)
        assert match is not None, f"Missing violation for {file_path}: {violations}"
        assert any(p in match for p in patterns), (
            f"Violation for {file_path} missing expected pattern {patterns}: {match}"
        )


def test_loop_subprocess_boundary_rule_errors_when_config_file_is_missing(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    missing_policy = tmp_path / "missing-loop-subprocess-policy.yaml"
    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=missing_policy,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.loop-subprocess-boundary"
    assert payload["status"] == "error"
    assert payload["violations"] == []
    summary = payload["summary"]
    assert isinstance(summary, str)
    assert "Native subprocess-boundary scan failed:" in summary


def test_loop_subprocess_boundary_rule_errors_when_config_file_is_invalid(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/placeholder.py",
        "def noop() -> None:\n    return None\n",
    )
    invalid_policy = tmp_path / "invalid-loop-subprocess-policy.yaml"
    invalid_policy.write_text(
        "\n".join(
            [
                "allowlisted_modules: not-a-list",
                "subprocess_call_names: [run]",
            ]
        ),
        encoding="utf-8",
    )
    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=invalid_policy,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.loop-subprocess-boundary"
    assert payload["status"] == "error"
    assert payload["violations"] == []
    summary = payload["summary"]
    assert isinstance(summary, str)
    assert summary.startswith("Native subprocess-boundary scan failed:")
