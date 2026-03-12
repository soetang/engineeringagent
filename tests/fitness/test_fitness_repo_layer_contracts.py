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


def test_repo_layer_contracts_rule_blocks_deleted_bootstrap_runtime_execution_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed bootstrap runtime execution module reappears."""
    bootstrap_root = tmp_path / "src" / "engineeringagent" / "bootstrap"
    bootstrap_root.mkdir(parents=True, exist_ok=True)
    (bootstrap_root / "runtime_execution.py").write_text(
        "import engineeringagent.loop\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/bootstrap/runtime_execution.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_runtime_support_loop_import(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when bootstrap runtime support reaches back into the loop facade."""
    bootstrap_root = tmp_path / "src" / "engineeringagent" / "bootstrap"
    bootstrap_root.mkdir(parents=True, exist_ok=True)
    (bootstrap_root / "runtime_support.py").write_text(
        "import engineeringagent.loop\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/bootstrap/runtime_support.py: bootstrap runtime support must not import the legacy engineeringagent.loop facade; call the canonical engineeringagent.adapters.agents boundary directly"
    ]


def test_repo_layer_contracts_rule_blocks_application_dynamic_imports_of_adapters(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when application modules hide forbidden adapter imports behind import_module."""
    application_root = tmp_path / "src" / "engineeringagent" / "application"
    application_root.mkdir(parents=True, exist_ok=True)
    (application_root / "feature_iteration_service.py").write_text(
        "\n".join(
            [
                "from importlib import import_module",
                "",
                'runtime = import_module("engineeringagent.adapters.progress")',
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
        "src/engineeringagent/application/feature_iteration_service.py: application modules must not import adapters, agents, bootstrap, or presentation modules"
    ]


def test_repo_layer_contracts_rule_blocks_runtime_support_loop_agent_runner_bridge(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when bootstrap runtime support reintroduces a loop-local agent bridge."""
    bootstrap_root = tmp_path / "src" / "engineeringagent" / "bootstrap"
    bootstrap_root.mkdir(parents=True, exist_ok=True)
    (bootstrap_root / "runtime_support.py").write_text(
        "class _LoopAgentRunner:\n    pass\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/bootstrap/runtime_support.py: bootstrap runtime support must not declare _LoopAgentRunner; use AppFactory.build_agent_runner() and the adapters.agents boundary"
    ]


def test_repo_layer_contracts_rule_allows_application_iteration_pipeline_contracts(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the application iteration pipeline to import local contracts."""
    application_root = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "feature_iteration"
    )
    application_root.mkdir(parents=True, exist_ok=True)
    (application_root / "pipeline.py").write_text(
        "from .contracts import IterationReport\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_repo_layer_contracts_rule_blocks_document_adapters_importing_application(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when document adapters depend on application-layer models."""
    documents_root = (
        tmp_path / "src" / "engineeringagent" / "adapters" / "documents"
    )
    documents_root.mkdir(parents=True, exist_ok=True)
    (documents_root / "filesystem_feature_state.py").write_text(
        "from engineeringagent.application.run_loop_service import RunLoopRequest\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/adapters/documents/filesystem_feature_state.py: document adapters must not import application modules"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_audit_iteration_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed audit iteration module reappears."""
    audit_root = tmp_path / "src" / "engineeringagent" / "domain" / "audit"
    audit_root.mkdir(parents=True, exist_ok=True)
    (audit_root / "iteration.py").write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/domain/audit/iteration.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_top_level_config_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed top-level config module reappears."""
    package_root = tmp_path / "src" / "engineeringagent"
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "config.py").write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/config.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_allows_quality_runtime_bridge(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow the quality runtime adapter to compose checks internals."""
    runtime_module = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "adapters"
        / "quality"
        / "runtime.py"
    )
    runtime_module.parent.mkdir(parents=True, exist_ok=True)
    runtime_module.write_text(
        "\n".join(
            [
                "from engineeringagent.adapters.quality.config_selection import load_selected_harness_checks_document",
                "from engineeringagent.adapters.quality.check_strategies import CommandCheckStrategy",
                "",
                "__all__ = ['load_selected_harness_checks_document', 'CommandCheckStrategy']",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_repo_layer_contracts_rule_blocks_deleted_application_checks_runtime(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed application checks runtime module reappears."""
    legacy_runtime = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "checks"
        / "runtime.py"
    )
    legacy_runtime.parent.mkdir(parents=True, exist_ok=True)
    legacy_runtime.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/application/checks/runtime.py: deleted legacy module path must remain absent",
        "src/engineeringagent/application/checks: deleted legacy directory path must remain absent",
    ]


def test_repo_layer_contracts_rule_blocks_deleted_runtime_feature_iteration_workflow(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the deleted adapter-owned feature iteration workflow reappears."""
    legacy_workflow = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "adapters"
        / "runtime"
        / "feature_iteration_workflow.py"
    )
    legacy_workflow.parent.mkdir(parents=True, exist_ok=True)
    legacy_workflow.write_text("", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/adapters/runtime/feature_iteration_workflow.py: deleted legacy module path must remain absent"
    ]


def test_repo_layer_contracts_rule_blocks_prompt_models_in_port_repository_module(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when prompt contract models are reintroduced into the port module."""
    ports_root = tmp_path / "src" / "engineeringagent" / "ports"
    ports_root.mkdir(parents=True, exist_ok=True)
    (ports_root / "prompt_definition_repository.py").write_text(
        "\n".join(
            [
                "from typing import Protocol",
                "from pydantic import BaseModel",
                "",
                "class PromptDefinition(BaseModel):",
                "    prompt_id: str",
                "",
                "class PromptDefinitionRepository(Protocol):",
                "    def get(self, prompt_id: str) -> PromptDefinition: ...",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["rule_id"] == "architecture.repo-layer-contracts"
    assert payload["violations"] == [
        "src/engineeringagent/ports/prompt_definition_repository.py: prompt-definition ports module must declare only the PromptDefinitionRepository Protocol; move prompt models into domain contracts"
    ]


def test_repo_layer_contracts_rule_blocks_deleted_application_contracts_directory(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed application contracts package reappears."""
    contracts_root = tmp_path / "src" / "engineeringagent" / "application" / "contracts"
    contracts_root.mkdir(parents=True, exist_ok=True)
    (contracts_root / "__init__.py").write_text("", encoding="utf-8")
    (contracts_root / "run_loop.py").write_text("class RunLoopRequest:\n    pass\n", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "src/engineeringagent/application/contracts/__init__.py: deleted legacy module path must remain absent",
        "src/engineeringagent/application/contracts/run_loop.py: deleted legacy module path must remain absent",
        "src/engineeringagent/application/contracts: deleted legacy directory path must remain absent",
    ]
