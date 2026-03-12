from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.application-root-workflow-surface"
PROJECT_ROOT = Path(".")
APPLICATION_ROOT = PROJECT_ROOT / "src" / "engineeringagent" / "application" / "__init__.py"
FEATURE_ITERATION_ROOT = (
    PROJECT_ROOT / "src" / "engineeringagent" / "application" / "feature_iteration" / "__init__.py"
)
FORBIDDEN_EXPORT_MODULES = {
    "checks_service",
    "feature_iteration",
    "feature_iteration_service",
    "guidance_service",
    "init_workspace_service",
    "prompt_builder",
    "run_loop",
    "run_loop_service",
    "validation_service",
    "workspace_recovery_service",
}
FORBIDDEN_ROOT_EXPORTS = frozenset(
    {
        "CommandTiming",
        "CompletionCommitOutcome",
        "FeatureIterationDependencies",
        "FeatureIterationRequest",
        "FeatureIterationResult",
        "FeatureIterationInputs",
        "GuidanceInputError",
        "GuidanceQuery",
        "GuidanceResult",
        "GatePhaseOutcome",
        "ImplementationPromptRequest",
        "ImplementStepInputs",
        "ImplementStepOutputDependencies",
        "ImplementStepResult",
        "ImplementStepRuntimeDependencies",
        "InitWorkspaceRequest",
        "InitWorkspaceResult",
        "IterationOutcome",
        "IterationPipelineDependencies",
        "IterationReport",
        "IterationSummaryInputs",
        "IterationTelemetryInputs",
        "PhaseTiming",
        "ReviewerPhaseOutcome",
        "LoopRun",
        "RecoverWorkspaceRequest",
        "RecoverWorkspaceResult",
        "RunConfig",
        "RunChecksRequest",
        "RunChecksResult",
        "RunLoopRequest",
        "RunLoopResult",
        "RunServices",
        "RunState",
        "ValidateRepositoryRequest",
        "ValidationResult",
        "VerificationPhaseOutcome",
        "run_feature_iteration_pipeline",
        "run_implement_step_from_inputs",
    }
)
SCAN_ROOTS = (
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "tests",
)
SKIP_DIR_NAMES = {"__pycache__", ".venv"}
FEATURE_ITERATION_PACKAGE = "engineeringagent.application.feature_iteration"
FORBIDDEN_FEATURE_ITERATION_EXPORT_MODULES = {
    "contracts",
    "implementation_step",
    "pipeline",
    "runtime_dependencies",
}
FORBIDDEN_FEATURE_ITERATION_EXPORTS = frozenset(
    {
        "CommandTiming",
        "CompletionCommitOutcome",
        "FeatureIterationDependencies",
        "FeatureIterationInputs",
        "GatePhaseOutcome",
        "ImplementStepFailureDependencies",
        "ImplementStepInputs",
        "ImplementStepOutputDependencies",
        "ImplementStepResult",
        "ImplementStepRuntimeDependencies",
        "IterationOutcome",
        "IterationPipelineDependencies",
        "IterationReport",
        "IterationReportPublisher",
        "IterationSummaryInputs",
        "IterationTelemetryInputs",
        "PhaseTiming",
        "ReviewerPhaseOutcome",
        "VerificationPhaseOutcome",
        "build_feature_iteration_pipeline_dependencies",
        "run_feature_iteration_pipeline",
        "run_implement_step_from_inputs",
    }
)


def _iter_python_files() -> tuple[Path, ...]:
    paths: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            paths.append(path)
    return tuple(sorted(set(paths)))


def _parse_file(path: Path) -> tuple[ast.AST | None, list[str]]:
    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"{rel_path}: failed to read python module: {exc}"]
    try:
        return ast.parse(source, filename=rel_path), []
    except SyntaxError as exc:
        detail = str(exc.msg).strip() or "invalid syntax"
        return None, [f"{rel_path}:{exc.lineno or 1} failed to parse: {detail}"]


def _root_export_violations(path: Path) -> list[str]:
    tree, parse_errors = _parse_file(path)
    if tree is None:
        return parse_errors

    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    violations: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module in FORBIDDEN_EXPORT_MODULES
        ):
            for alias in node.names:
                if alias.name in FORBIDDEN_ROOT_EXPORTS:
                    violations.append(
                        f"{rel_path}:{node.lineno} application root must not re-export "
                        f"{node.module} symbol {alias.name}"
                    )
        elif isinstance(node, ast.Assign):
            if not any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                continue
            for exported_name in _string_list_members(node.value):
                if exported_name in FORBIDDEN_ROOT_EXPORTS:
                    violations.append(
                        f"{rel_path}:{node.lineno} application root __all__ must not include "
                        f"internal workflow symbol {exported_name}"
                    )
    return violations


def _string_list_members(node: ast.AST) -> tuple[str, ...]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return ()
    names: list[str] = []
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            names.append(element.value)
    return tuple(names)


def _root_import_violations(path: Path) -> list[str]:
    tree, parse_errors = _parse_file(path)
    if tree is None:
        return parse_errors

    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "engineeringagent.application":
            continue
        for alias in node.names:
            if alias.name in FORBIDDEN_ROOT_EXPORTS:
                defining_module = _defining_module_for(alias.name)
                violations.append(
                    f"{rel_path}:{node.lineno} import {alias.name} from "
                    f"{defining_module} instead of engineeringagent.application"
                )
    return violations


def _feature_iteration_export_violations(path: Path) -> list[str]:
    tree, parse_errors = _parse_file(path)
    if tree is None:
        return parse_errors

    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    violations: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module in FORBIDDEN_FEATURE_ITERATION_EXPORT_MODULES
        ):
            for alias in node.names:
                if alias.name in FORBIDDEN_FEATURE_ITERATION_EXPORTS:
                    violations.append(
                        f"{rel_path}:{node.lineno} feature_iteration package must not "
                        f"re-export internal workflow symbol {alias.name}"
                    )
        elif isinstance(node, ast.Assign):
            if not any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                continue
            for exported_name in _string_list_members(node.value):
                if exported_name in FORBIDDEN_FEATURE_ITERATION_EXPORTS:
                    violations.append(
                        f"{rel_path}:{node.lineno} feature_iteration package __all__ "
                        f"must not include internal workflow symbol {exported_name}"
                    )
    return violations


def _feature_iteration_import_violations(path: Path) -> list[str]:
    tree, parse_errors = _parse_file(path)
    if tree is None:
        return parse_errors

    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != FEATURE_ITERATION_PACKAGE:
            continue
        for alias in node.names:
            if alias.name in FORBIDDEN_FEATURE_ITERATION_EXPORTS:
                defining_module = _feature_iteration_defining_module_for(alias.name)
                violations.append(
                    f"{rel_path}:{node.lineno} import {alias.name} from "
                    f"{defining_module} instead of {FEATURE_ITERATION_PACKAGE}"
                )
    return violations


def _defining_module_for(symbol_name: str) -> str:
    if symbol_name in {
        "FeatureIterationDependencies",
        "FeatureIterationRequest",
        "FeatureIterationResult",
    }:
        return "engineeringagent.application.feature_iteration_service"
    if symbol_name in {
        "GuidanceInputError",
        "GuidanceQuery",
        "GuidanceResult",
    }:
        return "engineeringagent.application.guidance_service"
    if symbol_name == "ImplementationPromptRequest":
        return "engineeringagent.application.prompt_builder"
    if symbol_name in {"InitWorkspaceRequest", "InitWorkspaceResult"}:
        return "engineeringagent.application.init_workspace_service"
    if symbol_name in {"RecoverWorkspaceRequest", "RecoverWorkspaceResult"}:
        return "engineeringagent.application.workspace_recovery_service"
    if symbol_name in {"RunChecksRequest", "RunChecksResult"}:
        return "engineeringagent.application.checks_service"
    if symbol_name in {"RunLoopRequest", "RunLoopResult"}:
        return "engineeringagent.application.run_loop_service"
    if symbol_name in {"ValidateRepositoryRequest", "ValidationResult"}:
        return "engineeringagent.application.validation_service"
    return "its defining application module"


def _feature_iteration_defining_module_for(symbol_name: str) -> str:
    if symbol_name in {
        "CommandTiming",
        "CompletionCommitOutcome",
        "FeatureIterationInputs",
        "GatePhaseOutcome",
        "ImplementStepInputs",
        "ImplementStepResult",
        "IterationOutcome",
        "IterationReport",
        "IterationSummaryInputs",
        "IterationTelemetryInputs",
        "PhaseTiming",
        "ReviewerPhaseOutcome",
        "VerificationPhaseOutcome",
    }:
        return "engineeringagent.application.feature_iteration.contracts"
    if symbol_name in {
        "ImplementStepFailureDependencies",
        "ImplementStepOutputDependencies",
        "ImplementStepRuntimeDependencies",
        "run_implement_step_from_inputs",
    }:
        return "engineeringagent.application.feature_iteration.implementation_step"
    if symbol_name in {
        "IterationPipelineDependencies",
        "run_feature_iteration_pipeline",
    }:
        return "engineeringagent.application.feature_iteration.pipeline"
    if symbol_name in {
        "FeatureIterationDependencies",
        "IterationReportPublisher",
        "build_feature_iteration_pipeline_dependencies",
    }:
        return "engineeringagent.application.feature_iteration.runtime_dependencies"
    return "its defining feature-iteration module"


def _application_root_workflow_surface_violations() -> list[str]:
    violations = _root_export_violations(APPLICATION_ROOT)
    if FEATURE_ITERATION_ROOT.exists():
        violations.extend(_feature_iteration_export_violations(FEATURE_ITERATION_ROOT))
    for path in _iter_python_files():
        if path == APPLICATION_ROOT:
            continue
        violations.extend(_root_import_violations(path))
        if path != FEATURE_ITERATION_ROOT:
            violations.extend(_feature_iteration_import_violations(path))
    return sorted(set(violations))


def main() -> int:
    """Emit the application-root-workflow-surface fitness result."""
    violations = _application_root_workflow_surface_violations()
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "engineeringagent.application exposes workflow services only."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} application root workflow-surface violation(s)."
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
