from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)
from engineeringagent.checks import emit_fitness_result


RULE_ID = "architecture.application-root-workflow-surface"
PROJECT_ROOT = Path(".")
APPLICATION_ROOT = PROJECT_ROOT / "src" / "engineeringagent" / "application" / "__init__.py"
FEATURE_ITERATION_ROOT = (
    PROJECT_ROOT / "src" / "engineeringagent" / "application" / "feature_iteration" / "__init__.py"
)
SCAN_ROOTS = (PROJECT_ROOT / "src", PROJECT_ROOT / "tests")
SKIP_DIR_NAMES = {"__pycache__", ".venv"}
FEATURE_ITERATION_PACKAGE = "engineeringagent.application.feature_iteration"
FORBIDDEN_ROOT_EXPORTS = frozenset(
    {
        "ChecksService",
        "CommandTiming",
        "CompletionCommitOutcome",
        "FeatureIterationService",
        "FeatureIterationDependencies",
        "FeatureIterationInputs",
        "FeatureIterationRequest",
        "FeatureIterationResult",
        "GatePhaseOutcome",
        "GuidanceService",
        "GuidanceInputError",
        "GuidanceQuery",
        "GuidanceResult",
        "InitWorkspaceService",
        "ImplementationPromptRequest",
        "ImplementStepInputs",
        "ImplementStepResult",
        "InitWorkspaceRequest",
        "InitWorkspaceResult",
        "IterationOutcome",
        "IterationReport",
        "IterationTelemetryInputs",
        "PhaseTiming",
        "PromptBuilder",
        "RecoverWorkspaceRequest",
        "RecoverWorkspaceResult",
        "RunLoopService",
        "RunChecksRequest",
        "RunChecksResult",
        "RunLoopRequest",
        "RunLoopResult",
        "ValidationService",
        "ValidateRepositoryRequest",
        "ValidationResult",
        "VerificationPhaseOutcome",
        "ReviewerPhaseOutcome",
        "WorkspaceRecoveryService",
        "run_feature_iteration_pipeline",
    }
)
FORBIDDEN_FEATURE_ITERATION_EXPORTS = frozenset(
    {
        "CommandTiming",
        "CompletionCommitOutcome",
        "FeatureIterationInputs",
        "GatePhaseOutcome",
        "ImplementStepInputs",
        "ImplementStepResult",
        "IterationOutcome",
        "IterationReport",
        "IterationTelemetryInputs",
        "PhaseTiming",
        "ReviewerPhaseOutcome",
        "VerificationPhaseOutcome",
        "run_feature_iteration_pipeline",
    }
)
SYMBOL_MODULES = {
    "ChecksService": "engineeringagent.application.checks_service",
    "FeatureIterationService": "engineeringagent.application.feature_iteration_service",
    "FeatureIterationDependencies": "engineeringagent.application.feature_iteration_service",
    "FeatureIterationRequest": "engineeringagent.application.feature_iteration_service",
    "FeatureIterationResult": "engineeringagent.application.feature_iteration_service",
    "GuidanceService": "engineeringagent.application.guidance_service",
    "GuidanceInputError": "engineeringagent.application.guidance_service",
    "GuidanceQuery": "engineeringagent.application.guidance_service",
    "GuidanceResult": "engineeringagent.application.guidance_service",
    "InitWorkspaceService": "engineeringagent.application.init_workspace_service",
    "ImplementationPromptRequest": "engineeringagent.application.prompt_builder",
    "PromptBuilder": "engineeringagent.application.prompt_builder",
    "InitWorkspaceRequest": "engineeringagent.application.init_workspace_service",
    "InitWorkspaceResult": "engineeringagent.application.init_workspace_service",
    "RecoverWorkspaceRequest": "engineeringagent.application.workspace_recovery_service",
    "RecoverWorkspaceResult": "engineeringagent.application.workspace_recovery_service",
    "RunChecksRequest": "engineeringagent.application.checks_service",
    "RunChecksResult": "engineeringagent.application.checks_service",
    "RunLoopService": "engineeringagent.application.run_loop_service",
    "RunLoopRequest": "engineeringagent.application.run_loop_service",
    "RunLoopResult": "engineeringagent.application.run_loop_service",
    "ValidationService": "engineeringagent.application.validation_service",
    "ValidateRepositoryRequest": "engineeringagent.application.validation_service",
    "ValidationResult": "engineeringagent.application.validation_service",
    "WorkspaceRecoveryService": "engineeringagent.application.workspace_recovery_service",
}
FEATURE_ITERATION_SYMBOL_MODULES = {
    "CommandTiming": "engineeringagent.application.feature_iteration.contracts",
    "CompletionCommitOutcome": "engineeringagent.application.feature_iteration.contracts",
    "FeatureIterationInputs": "engineeringagent.application.feature_iteration.contracts",
    "GatePhaseOutcome": "engineeringagent.application.feature_iteration.contracts",
    "ImplementStepInputs": "engineeringagent.application.feature_iteration.contracts",
    "ImplementStepResult": "engineeringagent.application.feature_iteration.contracts",
    "IterationOutcome": "engineeringagent.application.feature_iteration.contracts",
    "IterationReport": "engineeringagent.application.feature_iteration.contracts",
    "IterationTelemetryInputs": "engineeringagent.application.feature_iteration.contracts",
    "PhaseTiming": "engineeringagent.application.feature_iteration.contracts",
    "ReviewerPhaseOutcome": "engineeringagent.application.feature_iteration.contracts",
    "VerificationPhaseOutcome": "engineeringagent.application.feature_iteration.contracts",
    "run_feature_iteration_pipeline": "engineeringagent.application.feature_iteration.pipeline",
}


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


def _string_list_members(node: ast.AST) -> tuple[str, ...]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return ()
    names: list[str] = []
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            names.append(element.value)
    return tuple(names)


def _package_export_violations(
    path: Path,
    *,
    forbidden_names: frozenset[str],
    package_label: str,
) -> list[str]:
    tree, parse_errors = _parse_file(path)
    if tree is None:
        return parse_errors

    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in forbidden_names:
                    violations.append(
                        f"{rel_path}:{node.lineno} {package_label} must not re-export "
                        f"internal workflow symbol {alias.name}"
                    )
        elif isinstance(node, ast.Assign):
            if not any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                continue
            for exported_name in _string_list_members(node.value):
                if exported_name in forbidden_names:
                    violations.append(
                        f"{rel_path}:{node.lineno} {package_label} __all__ must not "
                        f"include internal workflow symbol {exported_name}"
                    )
    return violations


def _import_violations(
    path: Path,
    *,
    package_name: str,
    symbol_modules: dict[str, str],
) -> list[str]:
    tree, parse_errors = _parse_file(path)
    if tree is None:
        return parse_errors

    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != package_name:
            continue
        for alias in node.names:
            defining_module = symbol_modules.get(alias.name)
            if defining_module is None:
                continue
            violations.append(
                f"{rel_path}:{node.lineno} import {alias.name} from "
                f"{defining_module} instead of {package_name}"
            )
    return violations


def _application_root_workflow_surface_violations() -> list[str]:
    violations: list[str] = []
    if APPLICATION_ROOT.exists():
        violations.extend(
            _package_export_violations(
                APPLICATION_ROOT,
                forbidden_names=FORBIDDEN_ROOT_EXPORTS,
                package_label="application root",
            )
        )
    if FEATURE_ITERATION_ROOT.exists():
        violations.extend(
            _package_export_violations(
                FEATURE_ITERATION_ROOT,
                forbidden_names=FORBIDDEN_FEATURE_ITERATION_EXPORTS,
                package_label="feature_iteration package",
            )
        )
    for path in _iter_python_files():
        if path == APPLICATION_ROOT or path == FEATURE_ITERATION_ROOT:
            continue
        violations.extend(
            _import_violations(
                path,
                package_name="engineeringagent.application",
                symbol_modules=SYMBOL_MODULES,
            )
        )
        violations.extend(
            _import_violations(
                path,
                package_name=FEATURE_ITERATION_PACKAGE,
                symbol_modules=FEATURE_ITERATION_SYMBOL_MODULES,
            )
        )
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
