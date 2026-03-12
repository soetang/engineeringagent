from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_repo_layer_contracts.py"
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


def test_repo_layer_contracts_rule_blocks_deleted_legacy_directory_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when a deleted legacy package directory reappears."""
    legacy_root = tmp_path / "src" / "engineeringagent" / "application" / "contracts"
    legacy_root.mkdir(parents=True, exist_ok=True)
    (legacy_root / "__pycache__").mkdir()

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/contracts: deleted legacy directory path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_loop_runtime_directory(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed loop_runtime package directory reappears."""
    legacy_root = tmp_path / "src" / "engineeringagent" / "loop_runtime"
    legacy_root.mkdir(parents=True, exist_ok=True)

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/loop_runtime: deleted legacy directory path must remain absent"
    ]


def test_repo_layer_contracts_rule_allows_application_workspace_directory(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the canonical application workspace package."""
    workspace_root = tmp_path / "src" / "engineeringagent" / "application" / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "__init__.py").write_text("", encoding="utf-8")
    (workspace_root / "init.py").write_text("", encoding="utf-8")
    (workspace_root / "recovery.py").write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == []


def test_repo_layer_contracts_rule_blocks_deleted_nested_validation_service_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed nested validation module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "validation"
        / "service.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/validation/service.py: deleted legacy module path must remain absent",
        "src/engineeringagent/application/validation: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_checks_adapter_directory(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the deleted checks adapter package reappears."""
    legacy_root = tmp_path / "src" / "engineeringagent" / "adapters" / "checks"
    legacy_root.mkdir(parents=True, exist_ok=True)
    (legacy_root / "__init__.py").write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/adapters/checks/__init__.py: deleted legacy module path must remain absent",
        "src/engineeringagent/adapters/checks: deleted legacy directory path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_configured_agent_runner_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed configured-agent wrapper module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "adapters"
        / "agents"
        / "configured_agent_runner.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/adapters/agents/configured_agent_runner.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_agents_registry_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed legacy agents registry module reappears."""
    legacy_module = tmp_path / "src" / "engineeringagent" / "agents" / "registry.py"
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/agents/registry.py: deleted legacy module path must remain absent",
        "src/engineeringagent/agents: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_agents_runtime_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed legacy agents runtime module reappears."""
    legacy_module = tmp_path / "src" / "engineeringagent" / "agents" / "runtime.py"
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/agents/runtime.py: deleted legacy module path must remain absent",
        "src/engineeringagent/agents: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_runtime_checks_runner_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed checks-runner wrapper module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "adapters"
        / "quality"
        / "runtime_checks_runner.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/adapters/quality/runtime_checks_runner.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_harness_toggle_shim_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when removed legacy harness toggle shims reappear."""
    legacy_fitness_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "checks"
        / "fitness"
        / "config.py"
    )
    legacy_fitness_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_fitness_module.write_text("", encoding="utf-8")
    legacy_pytest_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "checks"
        / "pytest"
        / "config.py"
    )
    legacy_pytest_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_pytest_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/checks/fitness/config.py: deleted legacy module path must remain absent",
        "src/engineeringagent/checks/pytest/config.py: deleted legacy module path must remain absent",
        "src/engineeringagent/checks/pytest: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_checks_planning_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when deleted checks planning helpers reappear under the legacy package."""
    matcher_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "checks"
        / "on_change_matcher.py"
    )
    matcher_module.parent.mkdir(parents=True, exist_ok=True)
    matcher_module.write_text("", encoding="utf-8")
    planning_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "checks"
        / "planning_policy.py"
    )
    planning_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/checks/on_change_matcher.py: deleted legacy module path must remain absent",
        "src/engineeringagent/checks/planning_policy.py: deleted legacy module path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_checks_strategy_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when deleted checks strategies reappear under the legacy package."""
    strategies_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "checks"
        / "strategies.py"
    )
    strategies_module.parent.mkdir(parents=True, exist_ok=True)
    strategies_module.write_text("", encoding="utf-8")
    strategy_contracts_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "checks"
        / "strategy_contracts.py"
    )
    strategy_contracts_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/checks/strategies.py: deleted legacy module path must remain absent",
        "src/engineeringagent/checks/strategy_contracts.py: deleted legacy module path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_checks_reviewer_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when reviewer execution helpers reappear under the legacy checks package."""
    engine_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "checks"
        / "reviewers"
        / "engine.py"
    )
    engine_module.parent.mkdir(parents=True, exist_ok=True)
    engine_module.write_text("", encoding="utf-8")
    runtime_module = engine_module.parent / "runtime.py"
    runtime_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/checks/reviewers/engine.py: deleted legacy module path must remain absent",
        "src/engineeringagent/checks/reviewers/runtime.py: deleted legacy module path must remain absent",
        "src/engineeringagent/checks/reviewers: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_legacy_run_loop_service_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed nested run-loop service module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "run_loop"
        / "service.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/run_loop/service.py: deleted legacy module path must remain absent",
        "src/engineeringagent/application/run_loop: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_bootstrap_feature_iteration_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when feature-iteration bootstrap assembly returns outside AppFactory."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "bootstrap"
        / "feature_iteration.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/bootstrap/feature_iteration.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_application_feature_selection_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed application feature-selection helper reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "feature_selection.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/feature_selection.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_application_feature_plan_progress_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed application plan-progress helper returns."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "feature_plan_progress.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/feature_plan_progress.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_loop_runtime_package_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed loop_runtime package module returns."""
    legacy_module = (
        tmp_path / "src" / "engineeringagent" / "loop_runtime" / "__init__.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/loop_runtime/__init__.py: deleted legacy module path must remain absent",
        "src/engineeringagent/loop_runtime: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_allows_canonical_checks_service_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the flat checks service module required by the target architecture."""
    canonical_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "checks_service.py"
    )
    canonical_module.parent.mkdir(parents=True, exist_ok=True)
    canonical_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_repo_layer_contracts_rule_blocks_deleted_application_checks_package(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed nested application checks package returns."""
    legacy_root = tmp_path / "src" / "engineeringagent" / "application" / "checks"
    legacy_root.mkdir(parents=True, exist_ok=True)
    (legacy_root / "__init__.py").write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/checks: deleted legacy directory path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_raw_feature_document_prompt_builder_entrypoint(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the application prompt builder restores raw feature-document input."""
    prompt_builder_path = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "prompt_builder.py"
    )
    prompt_builder_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_builder_path.write_text(
        "\n".join(
            [
                "class PromptBuilder:",
                "    def build_implementation_prompt_from_feature_document(self) -> str:",
                "        return 'legacy'",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/prompt_builder.py: prompt builder must not expose raw feature-document compatibility entrypoints"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_application_quality_package(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed application quality package reappears."""
    legacy_root = tmp_path / "src" / "engineeringagent" / "application" / "quality"
    legacy_root.mkdir(parents=True, exist_ok=True)
    (legacy_root / "checks_service.py").write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/quality/checks_service.py: deleted legacy module path must remain absent",
        "src/engineeringagent/application/quality: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_iteration_models_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed generic iteration-models module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "iteration_models.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/iteration_models.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_nested_guidance_service_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed nested guidance workflow module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "guidance"
        / "service.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/guidance/service.py: deleted legacy module path must remain absent",
        "src/engineeringagent/application/guidance: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_checks_changed_paths_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed checks changed_paths module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "checks"
        / "changed_paths.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/checks/changed_paths.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_loop_runtime_models_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed loop runtime models module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "loop_runtime"
        / "models.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/loop_runtime/models.py: deleted legacy module path must remain absent",
        "src/engineeringagent/loop_runtime: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_loop_runtime_feature_plan_state_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed loop-runtime plan-progress helper reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "loop_runtime"
        / "feature_plan_state.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/loop_runtime/feature_plan_state.py: deleted legacy module path must remain absent",
        "src/engineeringagent/loop_runtime: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_loop_runtime_implement_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed loop runtime implement module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "loop_runtime"
        / "implement.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/loop_runtime/implement.py: deleted legacy module path must remain absent",
        "src/engineeringagent/loop_runtime: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_loop_runtime_iteration_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed loop-runtime iteration module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "loop_runtime"
        / "iteration.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/loop_runtime/iteration.py: deleted legacy module path must remain absent",
        "src/engineeringagent/loop_runtime: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_loop_runtime_run_builder_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed loop runtime run-builder module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "loop_runtime"
        / "run_builder.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/loop_runtime/run_builder.py: deleted legacy module path must remain absent",
        "src/engineeringagent/loop_runtime: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_loop_runtime_run_context_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed loop runtime run-context module reappears."""
    legacy_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "loop_runtime"
        / "run_context.py"
    )
    legacy_module.parent.mkdir(parents=True, exist_ok=True)
    legacy_module.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/loop_runtime/run_context.py: deleted legacy module path must remain absent",
        "src/engineeringagent/loop_runtime: deleted legacy directory path must remain absent",
    ]
