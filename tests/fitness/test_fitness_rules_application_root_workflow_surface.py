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
                "from .feature_iteration import FeatureIterationInputs",
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
                "from .feature_iteration import FeatureIterationDependencies",
                "",
                '__all__ = ["FeatureIterationDependencies"]',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert any(
        "src/engineeringagent/application/__init__.py:1" in violation
        and "FeatureIterationDependencies" in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/application/__init__.py:3" in violation
        and "FeatureIterationDependencies" in violation
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
    """Reject callers importing feature-iteration contracts from the root package."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .feature_iteration_service import FeatureIterationRequest",
                "",
                '__all__ = ["FeatureIterationRequest"]',
                "",
            ]
        ),
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
    assert payload["status"] == "fail"
    assert any(
        "src/engineeringagent/application/__init__.py:1" in violation
        and "FeatureIterationRequest" in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/application/__init__.py:3" in violation
        and "FeatureIterationRequest" in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/adapters/runtime/execution.py:1" in violation
        and "engineeringagent.application.feature_iteration_service" in violation
        for violation in _violations(payload)
    )


def test_checker_flags_run_loop_request_from_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject callers importing run-loop contracts from the root package."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .contracts.run_loop import RunLoopRequest",
                "",
                '__all__ = ["RunLoopRequest"]',
                "",
            ]
        ),
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/contracts/run_loop.py",
        content="class RunLoopRequest:\n    pass\n",
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
    assert any(
        "src/engineeringagent/application/__init__.py:1" in violation
        and "RunLoopRequest" in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/application/__init__.py:3" in violation
        and "RunLoopRequest" in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/presentation/cli/run.py:1" in violation
        and "engineeringagent.application.contracts.run_loop" in violation
        for violation in _violations(payload)
    )


def test_checker_flags_checks_request_from_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject callers importing checks contracts from the root package."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content="\n".join(
            [
                "from .contracts.checks import RunChecksRequest",
                "",
                '__all__ = ["RunChecksRequest"]',
                "",
            ]
        ),
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/contracts/checks.py",
        content="class RunChecksRequest:\n    pass\n",
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/presentation/cli/checks.py",
        content="\n".join(
            [
                "from engineeringagent.application import RunChecksRequest",
                "",
                "REQUEST = RunChecksRequest",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert any(
        "src/engineeringagent/application/__init__.py:1" in violation
        and "RunChecksRequest" in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/presentation/cli/checks.py:1" in violation
        and "engineeringagent.application.contracts.checks" in violation
        for violation in _violations(payload)
    )


def test_checker_flags_run_loop_request_imported_from_service_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject direct imports of workflow contracts from service modules."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content='__all__ = ["RunLoopService"]\n',
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
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/presentation/cli/run.py:1 import RunLoopRequest from engineeringagent.application.contracts.run_loop instead of engineeringagent.application.run_loop_service"
    ]


def test_checker_flags_service_module_contract_definitions(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject restoring workflow request/result models to service modules."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content='__all__ = ["ChecksService"]\n',
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/checks_service.py",
        content="class RunChecksRequest:\n    pass\nclass RunChecksResult:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/checks_service.py:1 workflow request/result contracts must live under engineeringagent.application.contracts, not service modules",
        "src/engineeringagent/application/checks_service.py:3 workflow request/result contracts must live under engineeringagent.application.contracts, not service modules",
    ]


def test_checker_allows_feature_iteration_request_from_service_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the public request/result contracts to come from the service module."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content='__all__ = ["FeatureIterationService"]\n',
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/feature_iteration_service.py",
        content="\n".join(
            [
                "class FeatureIterationRequest:\n    pass\n",
                "class FeatureIterationResult:\n    pass\n",
            ]
        ),
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/adapters/runtime/execution.py",
        content="\n".join(
            [
                "from engineeringagent.application.feature_iteration_service import FeatureIterationRequest, FeatureIterationResult",
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


def test_checker_flags_feature_iteration_barrel_re_exports(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject re-exporting feature-iteration internals through the package barrel."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/__init__.py",
        content='__all__ = ["RunLoopService"]\n',
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/feature_iteration/__init__.py",
        content="\n".join(
            [
                "from .contracts import FeatureIterationInputs",
                "",
                '__all__ = ["FeatureIterationInputs"]',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert any(
        "src/engineeringagent/application/feature_iteration/__init__.py:1" in violation
        and "must not re-export internal workflow symbol FeatureIterationInputs"
        in violation
        for violation in _violations(payload)
    )
    assert any(
        "src/engineeringagent/application/feature_iteration/__init__.py:3" in violation
        and "__all__ must not include internal workflow symbol FeatureIterationInputs"
        in violation
        for violation in _violations(payload)
    )


def test_checker_flags_feature_iteration_barrel_imports(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject importing feature-iteration internals from the package barrel."""
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
                "from engineeringagent.application.feature_iteration import FeatureIterationInputs",
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
        and "engineeringagent.application.feature_iteration.contracts" in violation
        for violation in _violations(payload)
    )


def test_checker_allows_feature_iteration_direct_module_imports(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow consumers to import feature-iteration internals from defining modules."""
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
                "from engineeringagent.application.feature_iteration.contracts import FeatureIterationInputs",
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
