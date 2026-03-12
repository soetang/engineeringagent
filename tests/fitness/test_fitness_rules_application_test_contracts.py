from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_application_tests_boundary.py"
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


def _violations(payload: dict[str, object]) -> list[str]:
    return cast(list[str], payload["violations"])


def _write_test_module(project_root: Path, *, relative_path: str, content: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_checker_flags_legacy_checks_imports_in_application_tests(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when application tests depend on engineeringagent.checks modules."""
    _write_test_module(
        tmp_path,
        relative_path="tests/application/test_boundary_violation.py",
        content="\n".join(
            [
                "from engineeringagent.checks import HarnessCheckPhase",
                "",
                "def test_placeholder() -> None:",
                "    assert HarnessCheckPhase.ITERATION_END.value == 'iteration_end'",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.application-tests-boundary"
    assert payload["status"] == "fail"
    assert any(
        "tests/application/test_boundary_violation.py:1" in violation
        and "engineeringagent.checks" in violation
        for violation in _violations(payload)
    )


def test_checker_flags_adapter_imports_in_application_tests(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when application tests depend on adapter modules."""
    _write_test_module(
        tmp_path,
        relative_path="tests/application/test_boundary_violation.py",
        content="\n".join(
            [
                "from engineeringagent.adapters.progress import filesystem_journal",
                "",
                "def test_placeholder() -> None:",
                "    assert filesystem_journal is not None",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.application-tests-boundary"
    assert payload["status"] == "fail"
    assert any(
        "tests/application/test_boundary_violation.py:1" in violation
        and "engineeringagent.adapters.progress" in violation
        for violation in _violations(payload)
    )


def test_checker_flags_dynamic_adapter_imports_in_application_tests(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when application tests hide adapter imports behind import_module."""
    _write_test_module(
        tmp_path,
        relative_path="tests/application/test_boundary_violation.py",
        content="\n".join(
            [
                "import importlib",
                "",
                'MODULE = importlib.import_module("engineeringagent." "adapters.documents.filesystem_feature_state")',
                "",
                "def test_placeholder() -> None:",
                "    assert MODULE is not None",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.application-tests-boundary"
    assert payload["status"] == "fail"
    assert any(
        "tests/application/test_boundary_violation.py:3" in violation
        and "engineeringagent.adapters.documents.filesystem_feature_state" in violation
        for violation in _violations(payload)
    )


def test_checker_allows_application_tests_on_domain_and_ports_contracts(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow application tests that depend on application/domain/ports surfaces."""
    _write_test_module(
        tmp_path,
        relative_path="tests/application/test_boundary_ok.py",
        content="\n".join(
            [
                "from engineeringagent.application import RunChecksRequest",
                "from engineeringagent.domain.quality import HarnessCheckPhase",
                "from engineeringagent.ports import ChecksRunRequest",
                "",
                "def test_placeholder() -> None:",
                "    assert RunChecksRequest is not None",
                "    assert ChecksRunRequest is not None",
                "    assert HarnessCheckPhase.ITERATION_END.value == 'iteration_end'",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []
