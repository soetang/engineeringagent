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


def test_checker_flags_feature_iteration_re_exports_from_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject feature-iteration re-exports from the application root package."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .feature_iteration_runtime import FeatureIterationInputs",
                "",
                '__all__ = ["FeatureIterationInputs"]',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.application-root-workflow-surface"
    assert payload["status"] == "fail"
    assert any(
        "src/engineeringagent/application/__init__.py:1" in violation
        and "must not re-export" in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/application/__init__.py:3" in violation
        and "__all__ must not include" in violation
        for violation in _violations(payload)
    )


def test_checker_flags_feature_iteration_dependencies_on_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject runtime wiring helpers on the application root surface."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .feature_iteration_runtime import FeatureIterationRuntimeDependencies",
                "",
                '__all__ = ["FeatureIterationRuntimeDependencies"]',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert any(
        "src/engineeringagent/application/__init__.py:1" in violation
        and "FeatureIterationRuntimeDependencies" in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/application/__init__.py:3" in violation
        and "FeatureIterationRuntimeDependencies" in violation
        for violation in _violations(payload)
    )


def test_checker_flags_feature_iteration_imports_from_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject callers importing feature-iteration internals from the root package."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content='__all__ = ["RunLoopService"]\n',
    )
    _write_module(
        tmp_path,
        relative_path="tests/loop/test_boundary_violation.py",
        content="\n".join(
            [
                "from engineeringagent.application import FeatureIterationInputs",
                "",
                "def test_placeholder() -> None:",
                "    assert FeatureIterationInputs is not None",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert any(
        "tests/loop/test_boundary_violation.py:1" in violation
        and "its defining application module instead of engineeringagent.application"
        in violation
        for violation in _violations(payload)
    )


def test_checker_flags_feature_iteration_request_from_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow callers importing the public feature-iteration request from the root package."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="class FeatureIterationRequest:\n    pass\n",
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/feature_iteration_service.py",
        content="class FeatureIterationRequest:\n    pass\n",
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/adapters/runtime/execution.py",
        content="\n".join(
            [
                "from engineeringagent.application import FeatureIterationRequest",
                "",
                "REQUEST = FeatureIterationRequest",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_feature_iteration_request_re_exported_from_subpackage(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the public request/result contracts to come from the subpackage."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .feature_iteration_runtime import FeatureIterationRequest, FeatureIterationResult",
                "",
                '__all__ = ["FeatureIterationRequest", "FeatureIterationResult"]',
                "",
            ]
        ),
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/adapters/runtime/execution.py",
        content="\n".join(
            [
                "from engineeringagent.application import FeatureIterationRequest, FeatureIterationResult",
                "",
                "REQUEST = FeatureIterationRequest",
                "RESULT = FeatureIterationResult",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_feature_iteration_imports_from_explicit_subpackage(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow consumers to import feature-iteration internals from its subpackage."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content='__all__ = ["RunLoopService"]\n',
    )
    _write_module(
        tmp_path,
        relative_path="tests/loop/test_boundary_ok.py",
        content="\n".join(
            [
                "from engineeringagent.application import RunLoopService",
                "from engineeringagent.application.feature_iteration_runtime import FeatureIterationInputs",
                "",
                "def test_placeholder() -> None:",
                "    assert RunLoopService is not None",
                "    assert FeatureIterationInputs is not None",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_workspace_service_exports_from_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow workspace services on the application export surface."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .init_workspace_service import InitWorkspaceService",
                "from .workspace_recovery_service import WorkspaceRecoveryService",
                "",
                '__all__ = ["InitWorkspaceService", "WorkspaceRecoveryService"]',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_flags_runtime_loop_context_exports_from_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject runtime loop context leaking through the application root package."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .run_loop import RunConfig",
                "",
                '__all__ = ["RunConfig"]',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert any(
        "src/engineeringagent/application/__init__.py:1" in violation
        and "RunConfig" in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/application/__init__.py:3" in violation
        and "RunConfig" in violation
        for violation in _violations(payload)
    )
