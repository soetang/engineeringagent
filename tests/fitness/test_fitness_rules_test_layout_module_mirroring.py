from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_test_layout_module_mirroring.py"
    )


def _policy_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "policies"
        / "test_layout_module_mirroring.yaml"
    )


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
    config_file: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path), "--config-file", str(config_file)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def _write_file(project_root: Path, relative_path: str, body: str = "") -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_test_layout_module_mirroring_rule_passes_with_module_mirroring_and_exceptions(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow mirrored test paths plus explicit policy exceptions."""
    _write_file(tmp_path, "tests/meta/test_meta_smoke.py", "")
    _write_file(tmp_path, "tests/fitness/test_rule_smoke.py", "")
    _write_file(tmp_path, "tests/fixtures/test_fixture_layout.py", "")
    _write_file(tmp_path, "tests/conftest.py", "")
    _write_file(tmp_path, "tests/__init__.py", "")
    _write_file(tmp_path, "tests/checks/reviewers/test_reviewers_runtime.py", "")
    _write_file(tmp_path, "src/engineeringagent/checks/reviewers/__init__.py", "")
    _write_file(tmp_path, "src/engineeringagent/adapters/agents/opencode.py", "")
    _write_file(tmp_path, "tests/adapters/agents/opencode/test_client.py", "")

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["rule_id"] == "architecture.test-layout-module-mirroring"
    assert result["status"] == "pass"
    assert _violations(result) == []


def test_test_layout_module_mirroring_rule_flags_root_alias_and_unmirrored_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject root tests, alias roots, and tests without mirrored source paths."""
    _write_file(tmp_path, "tests/test_root_layout.py", "")
    _write_file(tmp_path, "tests/meta/test_meta.py", "")
    _write_file(tmp_path, "tests/vcs/test_git_client.py", "")
    _write_file(tmp_path, "tests/agents/backends/test_unmirrored.py", "")
    _write_file(tmp_path, "tests/__init__.py", "")
    _write_file(tmp_path, "tests/conftest.py", "")
    _write_file(tmp_path, "src/engineeringagent/agents.py", "")

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"

    violations = sorted(_violations(result))
    assert violations == [
        "tests/agents/backends/test_unmirrored.py: not mirrored by src module path "
        "src/engineeringagent/agents/backends",
        "tests/test_root_layout.py: banned root-level test module; move into a module "
        "folder or explicit exception.",
        "tests/vcs/test_git_client.py: disallowed alias topic root 'vcs/'; use module-mirrored path.",
    ]


def test_test_layout_module_mirroring_rule_flags_flat_test_for_nested_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject a flat legacy test path for nested feature-iteration helpers."""
    _write_file(tmp_path, "tests/application/test_feature_iteration_pipeline.py", "")
    _write_file(tmp_path, "tests/__init__.py", "")
    _write_file(tmp_path, "tests/conftest.py", "")
    _write_file(tmp_path, "src/engineeringagent/application/__init__.py", "")
    _write_file(tmp_path, "src/engineeringagent/application/feature_iteration/__init__.py", "")
    _write_file(tmp_path, "src/engineeringagent/application/feature_iteration/pipeline.py", "")

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/application/test_feature_iteration_pipeline.py: legacy test path is forbidden; move it under the mirrored source module path."
    ]


def test_test_layout_module_mirroring_rule_flags_legacy_workspace_service_test_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject workspace tests that keep the pre-subpackage service filenames."""
    _write_file(tmp_path, "tests/application/workspace/test_init_workspace_service.py", "")
    _write_file(
        tmp_path,
        "tests/application/workspace/test_workspace_recovery_service.py",
        "",
    )
    _write_file(tmp_path, "tests/__init__.py", "")
    _write_file(tmp_path, "tests/conftest.py", "")
    _write_file(tmp_path, "src/engineeringagent/application/__init__.py", "")
    _write_file(tmp_path, "src/engineeringagent/application/init_workspace_service.py", "")
    _write_file(
        tmp_path,
        "src/engineeringagent/application/workspace_recovery_service.py",
        "",
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/application/workspace/test_init_workspace_service.py: legacy test path is forbidden; move it under the mirrored source module path.",
        "tests/application/workspace/test_workspace_recovery_service.py: legacy test path is forbidden; move it under the mirrored source module path.",
    ]


def test_test_layout_module_mirroring_rule_flags_legacy_bootstrap_adapter_test_path(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject adapter runtime tests kept under the legacy bootstrap topic."""
    _write_file(tmp_path, "tests/bootstrap/test_runtime_run_loop_executor.py", "")
    _write_file(tmp_path, "tests/__init__.py", "")
    _write_file(tmp_path, "tests/conftest.py", "")
    _write_file(tmp_path, "src/engineeringagent/bootstrap/__init__.py", "")
    _write_file(tmp_path, "src/engineeringagent/adapters/runtime/execution.py", "")

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/bootstrap/test_runtime_run_loop_executor.py: legacy test path is forbidden; move it under the mirrored source module path."
    ]


def test_test_layout_module_mirroring_rule_flags_legacy_progress_adapter_test_path(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject progress adapter tests kept under the legacy root topic."""
    _write_file(tmp_path, "tests/progress/test_filesystem_journal.py", "")
    _write_file(tmp_path, "tests/__init__.py", "")
    _write_file(tmp_path, "tests/conftest.py", "")
    _write_file(tmp_path, "src/engineeringagent/adapters/progress/__init__.py", "")
    _write_file(
        tmp_path,
        "src/engineeringagent/adapters/progress/filesystem_journal.py",
        "",
    )

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "tests/progress/test_filesystem_journal.py: legacy test path is forbidden; move it under the mirrored source module path."
    ]


def test_test_layout_module_mirroring_rule_allows_mirrored_test_for_feature_iteration_service(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow a mirrored test path for the root feature-iteration service module."""
    _write_file(tmp_path, "tests/application/test_feature_iteration_service.py", "")
    _write_file(tmp_path, "tests/__init__.py", "")
    _write_file(tmp_path, "tests/conftest.py", "")
    _write_file(tmp_path, "src/engineeringagent/application/__init__.py", "")
    _write_file(tmp_path, "src/engineeringagent/application/feature_iteration_service.py", "")

    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=_policy_path(repo_root),
    )

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []
