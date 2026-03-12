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
        / "check_application_root_workflow_surface.py"
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


def _write_module(project_root: Path, *, relative_path: str, content: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_checker_flags_root_barrel_re_exports_of_workflow_contracts(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the application root barrel re-exports workflow contracts."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .run_loop_service import RunLoopRequest",
                "",
                '__all__ = ["RunLoopRequest"]',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.application-root-workflow-surface"
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/__init__.py:1 application root must not re-export internal workflow symbol RunLoopRequest",
        "src/engineeringagent/application/__init__.py:3 application root __all__ must not include internal workflow symbol RunLoopRequest",
    ]


def test_checker_flags_root_barrel_re_exports_of_workflow_services(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the application root barrel re-exports workflow services."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .checks_service import ChecksService",
                "",
                '__all__ = ["ChecksService"]',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/__init__.py:1 application root must not re-export internal workflow symbol ChecksService",
        "src/engineeringagent/application/__init__.py:3 application root __all__ must not include internal workflow symbol ChecksService",
    ]


def test_checker_flags_callers_importing_workflow_contracts_from_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when callers import workflow contracts from the application package root."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content='"""Application-layer workflow modules."""\n',
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/presentation/cli/run.py",
        content="\n".join(
            [
                "from engineeringagent.application import RunLoopRequest",
                "",
                "REQUEST = RunLoopRequest",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/presentation/cli/run.py:1 import RunLoopRequest from engineeringagent.application.run_loop_service instead of engineeringagent.application"
    ]


def test_checker_flags_callers_importing_workflow_services_from_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when callers import workflow services from the application package root."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content='"""Application-layer workflow modules."""\n',
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/bootstrap/app_factory.py",
        content="\n".join(
            [
                "from engineeringagent.application import ChecksService",
                "",
                "SERVICE = ChecksService",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/bootstrap/app_factory.py:1 import ChecksService from engineeringagent.application.checks_service instead of engineeringagent.application"
    ]


def test_checker_allows_direct_imports_from_service_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow callers to import workflow contracts from their service modules."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content='"""Application-layer workflow modules."""\n',
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/run_loop_service.py",
        content="class RunLoopRequest:\n    pass\n",
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/presentation/cli/run.py",
        content="\n".join(
            [
                "from engineeringagent.application.run_loop_service import RunLoopRequest",
                "",
                "REQUEST = RunLoopRequest",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_contract_definitions_inside_service_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow workflow request and result classes to live beside their services."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/checks_service.py",
        content="class RunChecksRequest:\n    pass\nclass RunChecksResult:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_flags_feature_iteration_barrel_re_exports(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the feature-iteration package re-exports internal workflow types."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/feature_iteration/__init__.py",
        content="\n".join(
            [
                "from .contracts import IterationReport",
                "",
                '__all__ = ["IterationReport"]',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/feature_iteration/__init__.py:1 feature_iteration package must not re-export internal workflow symbol IterationReport",
        "src/engineeringagent/application/feature_iteration/__init__.py:3 feature_iteration package __all__ must not include internal workflow symbol IterationReport",
    ]


def test_checker_flags_feature_iteration_package_imports(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when callers import feature-iteration internals from the package barrel."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/feature_iteration/__init__.py",
        content="__all__ = []\n",
    )
    _write_module(
        tmp_path,
        relative_path="tests/application/test_boundary_violation.py",
        content="\n".join(
            [
                "from engineeringagent.application.feature_iteration import IterationReport",
                "",
                "REPORT = IterationReport",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "tests/application/test_boundary_violation.py:1 import IterationReport from engineeringagent.application.feature_iteration.contracts instead of engineeringagent.application.feature_iteration"
    ]
