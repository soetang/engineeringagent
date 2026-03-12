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


RULE_ID = "architecture.application-tests-boundary"
PROJECT_ROOT = Path(".")
APPLICATION_TESTS_ROOT = PROJECT_ROOT / "tests" / "application"
FORBIDDEN_MODULE_PREFIXES = (
    "engineeringagent.adapters",
    "engineeringagent.checks",
)


def _iter_application_test_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(sorted(path for path in root.rglob("*.py") if path.is_file()))


def _scan_file(path: Path) -> list[str]:
    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{rel_path}: failed to read application test module: {exc}"]

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        detail = str(exc.msg).strip() or "invalid syntax"
        return [f"{rel_path}:{exc.lineno or 1} failed to parse: {detail}"]

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _append_forbidden_module_violation(
                    violations,
                    rel_path=rel_path,
                    lineno=node.lineno,
                    module_name=alias.name,
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module
            if module_name is None:
                continue
            _append_forbidden_module_violation(
                violations,
                rel_path=rel_path,
                lineno=node.lineno,
                module_name=module_name,
            )
        elif isinstance(node, ast.Call) and _is_dynamic_module_import(node):
            module_name = _literal_string_arg(node)
            if module_name is None:
                continue
            _append_forbidden_module_violation(
                violations,
                rel_path=rel_path,
                lineno=node.lineno,
                module_name=module_name,
            )
    return violations


def _append_forbidden_module_violation(
    violations: list[str],
    *,
    rel_path: str,
    lineno: int,
    module_name: str,
) -> None:
    if not _is_forbidden_module(module_name):
        return
    violations.append(
        f"{rel_path}:{lineno} application tests must use "
        "application/domain/ports contracts instead of "
        f"{module_name}"
    )


def _is_forbidden_module(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_MODULE_PREFIXES
    )


def _is_dynamic_module_import(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id in {"__import__", "import_module"}
    if isinstance(node.func, ast.Attribute):
        return (
            isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
            and node.func.attr == "import_module"
        )
    return False


def _literal_string_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    literal = node.args[0]
    if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
        return literal.value
    return None


def _application_test_boundary_violations(project_root: Path) -> list[str]:
    tests_root = project_root / "tests" / "application"
    violations: list[str] = []
    for path in _iter_application_test_files(tests_root):
        violations.extend(_scan_file(path))
    return sorted(set(violations))


def main() -> int:
    """Run the application-tests-boundary fitness rule."""
    violations = _application_test_boundary_violations(PROJECT_ROOT)
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Application tests use application/domain/ports contracts only."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} application-test boundary violation(s)."
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
