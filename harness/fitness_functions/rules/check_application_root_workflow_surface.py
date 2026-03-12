from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.application-root-workflow-surface"
PROJECT_ROOT = Path(".")
APPLICATION_ROOT = PROJECT_ROOT / "src" / "engineeringagent" / "application" / "__init__.py"
FORBIDDEN_ROOT_EXPORTS = frozenset(
    {
        "CommandTiming",
        "CompletionCommitOutcome",
        "FeatureIterationInputs",
        "GatePhaseOutcome",
        "ImplementStepInputs",
        "ImplementStepOutputDependencies",
        "ImplementStepResult",
        "ImplementStepRuntimeDependencies",
        "IterationOutcome",
        "IterationPipelineDependencies",
        "IterationReport",
        "IterationSummaryInputs",
        "IterationTelemetryInputs",
        "PhaseTiming",
        "ReviewerPhaseOutcome",
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
        if isinstance(node, ast.ImportFrom) and node.module == "feature_iteration":
            for alias in node.names:
                if alias.name in FORBIDDEN_ROOT_EXPORTS:
                    violations.append(
                        f"{rel_path}:{node.lineno} application root must not re-export "
                        f"feature_iteration symbol {alias.name}"
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
                        f"feature_iteration symbol {exported_name}"
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
                violations.append(
                    f"{rel_path}:{node.lineno} import {alias.name} from "
                    "engineeringagent.application.feature_iteration instead of "
                    "engineeringagent.application"
                )
    return violations


def _application_root_workflow_surface_violations() -> list[str]:
    violations = _root_export_violations(APPLICATION_ROOT)
    for path in _iter_python_files():
        if path == APPLICATION_ROOT:
            continue
        violations.extend(_root_import_violations(path))
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
