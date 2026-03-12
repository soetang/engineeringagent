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
        / "check_application_module_layout.py"
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


def test_checker_flags_legacy_flat_application_helper_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject feature-iteration helper modules restored at the application root."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/feature_selection.py",
        content="FEATURE = 'legacy'\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.application-module-layout"
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/feature_selection.py: application root may only contain workflow-service modules; keep only documented workflow-service modules at the application root; move helpers into an explicit subpackage such as engineeringagent.application.feature_iteration, or delete the legacy module"
    ]


def test_checker_allows_declared_workflow_services_at_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the target application service modules at the package root."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/run_loop_service.py",
        content="class RunLoopService:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_feature_iteration_service_at_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the documented root-level feature iteration service module."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/feature_iteration_service.py",
        content="class FeatureIterationService:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_helper_modules_inside_explicit_application_subpackages(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow helper modules to live in explicit application subpackages."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/feature_iteration/pipeline.py",
        content="def run_feature_iteration_pipeline() -> None:\n    pass\n",
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/feature_iteration/runtime_dependencies.py",
        content="class FeatureIterationDependencies:\n    pass\n",
    )
    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_prompt_builder_at_application_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the documented root-level prompt builder application service."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/prompt_builder.py",
        content="class PromptBuilder:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_root_validation_service_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the documented root-level validation workflow service."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/validation_service.py",
        content="class ValidationService:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_root_guidance_service_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the documented root-level guidance workflow service."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/guidance_service.py",
        content="class GuidanceService:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_allows_workspace_service_modules_in_workspace_subpackage(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject the removed workspace application subpackage."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/workspace/init_service.py",
        content="class InitWorkspaceService:\n    pass\n",
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/workspace/recovery_service.py",
        content="class WorkspaceRecoveryService:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/workspace: legacy workspace application package must remain absent; promote workspace workflow services to root-level application modules such as init_workspace_service.py and workspace_recovery_service.py"
    ]


def test_checker_flags_legacy_root_workspace_service_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the target root-level workspace service modules."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/init_workspace_service.py",
        content="class InitWorkspaceService:\n    pass\n",
    )
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/workspace_recovery_service.py",
        content="class WorkspaceRecoveryService:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []


def test_checker_flags_extra_workspace_modules_inside_workspace_subpackage(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject the legacy workspace package even when it only contains helpers."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/workspace/helpers.py",
        content="HELPER = True\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/workspace: legacy workspace application package must remain absent; promote workspace workflow services to root-level application modules such as init_workspace_service.py and workspace_recovery_service.py"
    ]


def test_checker_flags_legacy_run_loop_application_package(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject runtime loop context restored under the application layer."""
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/application/run_loop/context.py",
        content="class RunConfig:\n    pass\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/run_loop: runtime loop context belongs in engineeringagent.adapters.runtime; keep application focused on workflow services and move loop context models to a runtime adapter module"
    ]
