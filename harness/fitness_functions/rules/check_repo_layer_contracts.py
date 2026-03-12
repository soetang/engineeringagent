from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)

RULE_ID = "architecture.repo-layer-contracts"
PROJECT_ROOT = Path(".")
SRC_ROOT = PROJECT_ROOT / "src" / "engineeringagent"
APPLICATION_ROOT = SRC_ROOT / "application"
DOMAIN_ROOT = SRC_ROOT / "domain"
PORTS_ROOT = SRC_ROOT / "ports"
LOOP_RUNTIME_ROOT = SRC_ROOT / "loop_runtime"
OPENCODE_ALLOWED_ROOT = SRC_ROOT / "adapters" / "agents" / "opencode"
CONFIGURED_AGENT_RUNNER_ALLOWED_ROOTS = (
    SRC_ROOT / "bootstrap",
    SRC_ROOT / "adapters" / "agents",
)
AGENTS_ROOT = SRC_ROOT / "agents"
ADAPTERS_AGENTS_ROOT = SRC_ROOT / "adapters" / "agents"
ADAPTERS_DOCUMENTS_ROOT = SRC_ROOT / "adapters" / "documents"
BOOTSTRAP_RUNTIME_SUPPORT_PATH = SRC_ROOT / "bootstrap" / "runtime_support.py"
DELETED_MODULE_PATHS = {
    "src/engineeringagent/changed_paths.py",
    "src/engineeringagent/harness_checks_runtime.py",
    "src/engineeringagent/validator.py",
    "src/engineeringagent/ports/guidance_topics.py",
    "src/engineeringagent/ports/prompt_builder.py",
    "src/engineeringagent/ports/prompt_definitions.py",
    "src/engineeringagent/adapters/checks/__init__.py",
    "src/engineeringagent/adapters/checks/repository_validator.py",
    "src/engineeringagent/adapters/checks/runtime_checks_runner.py",
    "src/engineeringagent/adapters/quality/__init__.py",
    "src/engineeringagent/adapters/checks/filesystem_checks_catalog_repository.py",
    "src/engineeringagent/adapters/guidance/packaged_guidance_topics.py",
    "src/engineeringagent/adapters/prompts/bundled_prompt_definitions.py",
    "src/engineeringagent/adapters/prompts/filesystem_prompt_definitions.py",
    "src/engineeringagent/adapters/prompts/project_prompt_definitions.py",
    "src/engineeringagent/adapters/documents/filesystem_feature_selection.py",
    "src/engineeringagent/adapters/agents/configured_agent_runner.py",
    "src/engineeringagent/adapters/quality/runtime_checks_runner.py",
    "src/engineeringagent/application/contracts/__init__.py",
    "src/engineeringagent/application/contracts/checks.py",
    "src/engineeringagent/application/contracts/feature_iteration.py",
    "src/engineeringagent/application/contracts/guidance.py",
    "src/engineeringagent/application/contracts/init_workspace.py",
    "src/engineeringagent/application/contracts/prompt_builder.py",
    "src/engineeringagent/application/contracts/run_loop.py",
    "src/engineeringagent/application/contracts/validation.py",
    "src/engineeringagent/application/contracts/workspace_recovery.py",
    "src/engineeringagent/application/iteration_models.py",
    "src/engineeringagent/application/implementation_prompt.py",
    "src/engineeringagent/application/feature_plan_progress.py",
    "src/engineeringagent/application/feature_selection.py",
    "src/engineeringagent/application/guidance/__init__.py",
    "src/engineeringagent/application/guidance/contracts.py",
    "src/engineeringagent/application/guidance/service.py",
    "src/engineeringagent/application/feature_iteration_contracts.py",
    "src/engineeringagent/application/feature_iteration_pipeline.py",
    "src/engineeringagent/application/implementation_step.py",
    "src/engineeringagent/application/checks/runtime.py",
    "src/engineeringagent/application/init_workspace/service.py",
    "src/engineeringagent/application/quality/__init__.py",
    "src/engineeringagent/application/quality/checks_service.py",
    "src/engineeringagent/application/quality/validation_service.py",
    "src/engineeringagent/application/prompts/__init__.py",
    "src/engineeringagent/application/prompts/prompt_builder.py",
    "src/engineeringagent/application/run_loop/__init__.py",
    "src/engineeringagent/application/run_loop/service.py",
    "src/engineeringagent/application/validation/__init__.py",
    "src/engineeringagent/application/validation/service.py",
    "src/engineeringagent/application/workspace_recovery/__init__.py",
    "src/engineeringagent/application/workspace_recovery/service.py",
    "src/engineeringagent/agents/__init__.py",
    "src/engineeringagent/agents/contracts.py",
    "src/engineeringagent/agents/helpers.py",
    "src/engineeringagent/agents/opencode_preflight.py",
    "src/engineeringagent/bootstrap/feature_iteration.py",
    "src/engineeringagent/bootstrap/runtime_execution.py",
    "src/engineeringagent/domain/audit/iteration.py",
    "src/engineeringagent/domain/prompting/__init__.py",
    "src/engineeringagent/domain/prompting/prompt_definition.py",
    "src/engineeringagent/feature_commit.py",
    "src/engineeringagent/agents/registry.py",
    "src/engineeringagent/agents/runtime.py",
    "src/engineeringagent/checks/changed_paths.py",
    "src/engineeringagent/checks/contracts.py",
    "src/engineeringagent/checks/fitness/__init__.py",
    "src/engineeringagent/checks/fitness/adapters.py",
    "src/engineeringagent/checks/fitness/boundary_reporting.py",
    "src/engineeringagent/checks/fitness/catalog.py",
    "src/engineeringagent/checks/fitness/config.py",
    "src/engineeringagent/checks/fitness/contracts.py",
    "src/engineeringagent/checks/fitness/envelope.py",
    "src/engineeringagent/checks/fitness/local_support_loader.py",
    "src/engineeringagent/checks/on_change_matcher.py",
    "src/engineeringagent/checks/planning_policy.py",
    "src/engineeringagent/checks/pytest/config.py",
    "src/engineeringagent/checks/fitness/registry.py",
    "src/engineeringagent/checks/results.py",
    "src/engineeringagent/checks/fitness/runner.py",
    "src/engineeringagent/checks/strategies.py",
    "src/engineeringagent/checks/strategy_contracts.py",
    "src/engineeringagent/checks/fitness/runtime.py",
    "src/engineeringagent/checks/fitness/scope_traversal.py",
    "src/engineeringagent/checks/reviewers/engine.py",
    "src/engineeringagent/checks/reviewers/runtime.py",
    "src/engineeringagent/git/__init__.py",
    "src/engineeringagent/git/client.py",
    "src/engineeringagent/progress/__init__.py",
    "src/engineeringagent/progress/handoff.py",
    "src/engineeringagent/progress/paths.py",
    "src/engineeringagent/progress_paths.py",
    "src/engineeringagent/progress_logging.py",
    "src/engineeringagent/prompts/__init__.py",
    "src/engineeringagent/prompts/definitions/__init__.py",
    "src/engineeringagent/prompts/feedback_envelope.py",
    "src/engineeringagent/prompts/templates/__init__.py",
    "src/engineeringagent/spec_bundles.py",
    "src/engineeringagent/specs.py",
    "src/engineeringagent/config.py",
    "src/engineeringagent/loop_runtime/__init__.py",
    "src/engineeringagent/loop_runtime/controller.py",
    "src/engineeringagent/loop_runtime/feature_plan_state.py",
    "src/engineeringagent/loop_runtime/implement.py",
    "src/engineeringagent/loop_runtime/iteration.py",
    "src/engineeringagent/loop_runtime/models.py",
    "src/engineeringagent/loop_runtime/run_builder.py",
    "src/engineeringagent/loop_runtime/run_context.py",
}
DELETED_DIRECTORY_PATHS = {
    "src/engineeringagent/adapters/checks",
    "src/engineeringagent/application/checks",
    "src/engineeringagent/application/contracts",
    "src/engineeringagent/application/guidance",
    "src/engineeringagent/application/init_workspace",
    "src/engineeringagent/application/quality",
    "src/engineeringagent/application/loop_runtime",
    "src/engineeringagent/application/prompting",
    "src/engineeringagent/application/prompts",
    "src/engineeringagent/application/run_loop",
    "src/engineeringagent/application/validation",
    "src/engineeringagent/application/workspace",
    "src/engineeringagent/application/workspace_recovery",
    "src/engineeringagent/agents",
    "src/engineeringagent/checks/pytest",
    "src/engineeringagent/checks/reviewers",
    "src/engineeringagent/domain/prompting",
    "src/engineeringagent/loop_runtime",
}
LEGACY_MODULES = (
    "engineeringagent.changed_paths",
    "engineeringagent.git",
    "engineeringagent.git.client",
    "engineeringagent.progress_paths",
    "engineeringagent.progress_logging",
    "engineeringagent.spec_bundles",
    "engineeringagent.specs",
)
LEGACY_MEMBERS = {
    "changed_paths",
    "git",
    "progress_paths",
    "progress_logging",
    "spec_bundles",
    "specs",
}


def _iter_python_modules(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(
        sorted(path for path in root.rglob("*.py") if path.is_file() and path.name != "__init__.py")
    )


@lru_cache(maxsize=None)
def _parse_module(path: Path) -> ast.Module | str:
    rel_path = path.as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"{rel_path}: failed to read module: {exc}"
    try:
        return ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        detail = str(exc.msg).strip() or "invalid syntax"
        return f"{rel_path}: failed to parse module: {detail}"


def _matches_forbidden_module(module_name: str, forbidden_modules: tuple[str, ...]) -> bool:
    return any(
        module_name == forbidden_module or module_name.startswith(f"{forbidden_module}.")
        for forbidden_module in forbidden_modules
    )


def _is_allowed_module(
    module_name: str,
    allowed_modules: tuple[str, ...],
) -> bool:
    return any(
        module_name == allowed_module or module_name.startswith(f"{allowed_module}.")
        for allowed_module in allowed_modules
    )


def _forbidden_import_violations(
    module: ast.Module,
    *,
    rel_path: str,
    forbidden_modules: tuple[str, ...],
    message: str,
    allowed_modules: tuple[str, ...] = (),
) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(module):
        imported_module: str | None = None
        if isinstance(node, ast.ImportFrom):
            imported_module = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_allowed_module(alias.name, allowed_modules):
                    continue
                if _matches_forbidden_module(alias.name, forbidden_modules):
                    violations.append(f"{rel_path}: {message}")
            continue

        if imported_module is not None and _matches_forbidden_module(
            imported_module,
            forbidden_modules,
        ) and not _is_allowed_module(imported_module, allowed_modules):
            violations.append(f"{rel_path}: {message}")
    return violations


def _import_call_target_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            return f"{func.value.id}.{func.attr}"
    return None


def _forbidden_dynamic_import_violations(
    module: ast.Module,
    *,
    rel_path: str,
    forbidden_modules: tuple[str, ...],
    message: str,
    allowed_modules: tuple[str, ...] = (),
) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        target_name = _import_call_target_name(node)
        if target_name not in {"import_module", "importlib.import_module", "__import__"}:
            continue
        module_name = node.args[0]
        if not isinstance(module_name, ast.Constant) or not isinstance(module_name.value, str):
            continue
        if _is_allowed_module(module_name.value, allowed_modules):
            continue
        if _matches_forbidden_module(module_name.value, forbidden_modules):
            violations.append(f"{rel_path}: {message}")
    return violations


_LOOP_RUNTIME_ALLOWED_APPLICATION_IMPORTS: tuple[str, ...] = (
    "engineeringagent.application",
)


def _loop_runtime_violations(path: Path) -> list[str]:
    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    return [
        *_forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.application",),
            allowed_modules=_LOOP_RUNTIME_ALLOWED_APPLICATION_IMPORTS,
            message=(
                "loop runtime modules must not import application modules "
                "outside the application service surface"
            ),
        ),
        *_forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.bootstrap",),
            message="loop runtime modules must not import bootstrap modules",
        ),
    ]


def _is_protocol_base(base: ast.expr) -> bool:
    if isinstance(base, ast.Name):
        return base.id == "Protocol"
    if isinstance(base, ast.Attribute):
        return base.attr == "Protocol"
    return False


def _is_port_failure_base(base: ast.expr) -> bool:
    if isinstance(base, ast.Name):
        return base.id in {"Exception", "PortFailure"}
    if isinstance(base, ast.Attribute):
        return base.attr in {"Exception", "PortFailure"}
    return False


def _module_declares_port_contract(module: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ClassDef)
        and (
            any(_is_protocol_base(base) for base in node.bases)
            or any(_is_port_failure_base(base) for base in node.bases)
        )
        for node in module.body
    )


def _application_import_violations(module: ast.Module, *, rel_path: str) -> list[str]:
    return [
        *_forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.application",),
            message="ports modules must not import application modules",
        ),
        *_forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=(
                "engineeringagent.adapters",
                "engineeringagent.agents",
                "engineeringagent.bootstrap",
                "engineeringagent.presentation",
            ),
            message="ports modules must not import adapters, agents, bootstrap, or presentation modules",
        ),
        *_forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.specs",),
            message="ports modules must not import legacy specs modules",
        ),
        *_forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.init_scaffold",),
            message="application and ports modules must not import init_scaffold modules",
        ),
    ]


def _port_protocol_violations(path: Path) -> list[str]:
    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    violations = _application_import_violations(module, rel_path=rel_path)
    if not _module_declares_port_contract(module):
        violations.append(
            f"{rel_path}: ports modules must declare at least one Protocol contract or shared port failure"
        )
    if rel_path == "src/engineeringagent/ports/prompt_definition_repository.py":
        extra_class_names = sorted(
            node.name
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name != "PromptDefinitionRepository"
        )
        if extra_class_names:
            violations.append(
                f"{rel_path}: prompt-definition ports module must declare only the PromptDefinitionRepository Protocol; move prompt models into domain contracts"
            )
    return violations


def _application_module_violations(path: Path) -> list[str]:
    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    violations: list[str] = []
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and any(_is_protocol_base(base) for base in node.bases):
            violations.append(
                f"{rel_path}: application modules must not declare Protocol contracts"
            )
            break

    violations.extend(
        _forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.checks",),
            message="application modules must not import checks modules",
        )
    )
    violations.extend(
        _forbidden_dynamic_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.checks",),
            message="application modules must not import checks modules",
        )
    )
    violations.extend(
        _forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=(
                "engineeringagent.adapters",
                "engineeringagent.agents",
                "engineeringagent.bootstrap",
                "engineeringagent.presentation",
            ),
            message="application modules must not import adapters, agents, bootstrap, or presentation modules",
        )
    )
    violations.extend(
        _forbidden_dynamic_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=(
                "engineeringagent.adapters",
                "engineeringagent.agents",
                "engineeringagent.bootstrap",
                "engineeringagent.presentation",
            ),
            message="application modules must not import adapters, agents, bootstrap, or presentation modules",
        )
    )
    violations.extend(
        _forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.prompts",),
            message="application modules must not import legacy top-level prompts modules",
        )
    )
    violations.extend(
        _forbidden_dynamic_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.prompts",),
            message="application modules must not import legacy top-level prompts modules",
        )
    )
    violations.extend(
        _forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.init_scaffold",),
            message="application and ports modules must not import init_scaffold modules",
        )
    )
    violations.extend(
        _forbidden_dynamic_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.init_scaffold",),
            message="application and ports modules must not import init_scaffold modules",
        )
    )
    if rel_path == "src/engineeringagent/application/prompt_builder.py":
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef) and (
                node.name == "build_implementation_prompt_from_feature_document"
            ):
                violations.append(
                    f"{rel_path}: prompt builder must not expose raw feature-document compatibility entrypoints"
                )
                break
    return violations


def _documents_adapter_violations(path: Path) -> list[str]:
    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    return [
        *_forbidden_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.application",),
            message="document adapters must not import application modules",
        ),
        *_forbidden_dynamic_import_violations(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.application",),
            message="document adapters must not import application modules",
        ),
    ]


def _domain_module_violations(path: Path) -> list[str]:
    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    return _forbidden_import_violations(
        module,
        rel_path=rel_path,
        forbidden_modules=(
            "engineeringagent.adapters",
            "engineeringagent.application",
            "engineeringagent.bootstrap",
            "engineeringagent.ports",
            "engineeringagent.presentation",
            "engineeringagent.specs",
        ),
        message="domain modules must not import application, ports, adapters, presentation, bootstrap, or legacy specs modules",
    )


def _legacy_import_violations(path: Path) -> list[str]:
    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    violations: list[str] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in LEGACY_MODULES:
                    violations.append(
                        f"{rel_path}: production modules must not import deleted legacy module {alias.name}"
                    )
        if isinstance(node, ast.ImportFrom):
            if node.module in LEGACY_MODULES:
                violations.append(
                    f"{rel_path}: production modules must not import deleted legacy module {node.module}"
                )
            if node.module == "engineeringagent":
                for alias in node.names:
                    if alias.name in LEGACY_MEMBERS:
                        violations.append(
                            f"{rel_path}: production modules must not import deleted legacy member engineeringagent.{alias.name}"
                        )
    return violations


def _is_under(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _start_agent_boundary_violations(path: Path) -> list[str]:
    if _is_under(path, OPENCODE_ALLOWED_ROOT):
        return []

    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    violations: list[str] = []
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom):
            imported_module = node.module or ""
            if _matches_forbidden_module(
                imported_module,
                ("engineeringagent.adapters.agents.opencode",),
            ) and any(alias.name == "start_agent" for alias in node.names):
                violations.append(
                    f"{rel_path}: production modules must not import start_agent outside the opencode backend adapter"
                )
        if isinstance(node, ast.Attribute) and node.attr == "start_agent":
            violations.append(
                f"{rel_path}: production modules must not reference start_agent outside the opencode backend adapter"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "start_agent":
            violations.append(
                f"{rel_path}: production modules must not call start_agent outside the opencode backend adapter"
            )
    return violations


def _configured_agent_runner_boundary_violations(path: Path) -> list[str]:
    if any(_is_under(path, allowed_root) for allowed_root in CONFIGURED_AGENT_RUNNER_ALLOWED_ROOTS):
        return []

    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    violations: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.ImportFrom):
            continue
        if (node.module or "") in {
            "engineeringagent.adapters.agents",
            "engineeringagent.adapters.agents.configured_agent_runner",
        } and any(alias.name == "ConfiguredAgentRunner" for alias in node.names):
            violations.append(
                f"{rel_path}: production modules must not import ConfiguredAgentRunner outside bootstrap or adapters.agents"
            )
    return violations


def _json_format_boundary_violations(path: Path) -> list[str]:
    if _is_under(path, ADAPTERS_AGENTS_ROOT):
        return []

    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    violations: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if any(
            keyword.arg == "format"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "json"
            for keyword in node.keywords
        ):
            violations.append(
                f'{rel_path}: production modules must not pass format="json" outside adapters.agents modules'
            )
    return violations


def _bootstrap_runtime_support_violations(path: Path) -> list[str]:
    rel_path = path.as_posix()
    module = _parse_module(path)
    if isinstance(module, str):
        return [module]

    violations = _forbidden_import_violations(
        module,
        rel_path=rel_path,
        forbidden_modules=("engineeringagent.loop",),
        message=(
            "bootstrap runtime support must not import the legacy engineeringagent.loop facade; "
            "call the canonical engineeringagent.adapters.agents boundary directly"
        ),
    )
    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name != "_LoopAgentRunner":
            continue
        violations.append(
            f"{rel_path}: bootstrap runtime support must not declare _LoopAgentRunner; "
            "use AppFactory.build_agent_runner() and the adapters.agents boundary"
        )
    return violations


def _deleted_path_violations() -> list[str]:
    return [
        f"{relative_path}: deleted legacy module path must remain absent"
        for relative_path in sorted(DELETED_MODULE_PATHS)
        if (PROJECT_ROOT / relative_path).exists()
    ] + [
        f"{relative_path}: deleted legacy directory path must remain absent"
        for relative_path in sorted(DELETED_DIRECTORY_PATHS)
        if (PROJECT_ROOT / relative_path).exists()
    ]


def _repo_layer_contract_violations() -> list[str]:
    deleted_paths = set(DELETED_MODULE_PATHS)
    violations: list[str] = []
    violations.extend(_deleted_path_violations())

    for path in _iter_python_modules(SRC_ROOT):
        if path.as_posix() not in deleted_paths:
            violations.extend(_legacy_import_violations(path))
        violations.extend(_start_agent_boundary_violations(path))
        violations.extend(_configured_agent_runner_boundary_violations(path))
        violations.extend(_json_format_boundary_violations(path))

    for path in _iter_python_modules(DOMAIN_ROOT):
        violations.extend(_domain_module_violations(path))

    for path in _iter_python_modules(APPLICATION_ROOT):
        violations.extend(_application_module_violations(path))

    for path in _iter_python_modules(ADAPTERS_DOCUMENTS_ROOT):
        violations.extend(_documents_adapter_violations(path))

    for path in sorted(PORTS_ROOT.glob("*.py")):
        if path.name == "__init__.py" or path.as_posix() in deleted_paths:
            continue
        violations.extend(_port_protocol_violations(path))

    for path in _iter_python_modules(LOOP_RUNTIME_ROOT):
        violations.extend(_loop_runtime_violations(path))

    if BOOTSTRAP_RUNTIME_SUPPORT_PATH.is_file():
        violations.extend(
            _bootstrap_runtime_support_violations(BOOTSTRAP_RUNTIME_SUPPORT_PATH)
        )

    return sorted(set(violations))


def main() -> int:
    """Run the repository layer-contracts fitness rule."""
    violations = _repo_layer_contract_violations()
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Repository layer and legacy-path contracts are satisfied."
        if status == RuleStatus.PASS
        else "Detected repository layer or legacy-path contract violations."
    )
    emit_fitness_result(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=RULE_ID,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
