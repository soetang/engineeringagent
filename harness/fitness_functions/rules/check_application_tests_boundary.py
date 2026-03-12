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


RULE_ID = "architecture.application-tests-boundary"
PROJECT_ROOT = Path(".")
APPLICATION_TESTS_ROOT = PROJECT_ROOT / "tests" / "application"
FORBIDDEN_MODULE = "engineeringagent.checks"


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
                module_name = alias.name
                if module_name == FORBIDDEN_MODULE or module_name.startswith(
                    f"{FORBIDDEN_MODULE}."
                ):
                    violations.append(
                        f"{rel_path}:{node.lineno} application tests must use "
                        "application/domain/ports contracts instead of "
                        f"{module_name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module
            if module_name is None:
                continue
            if module_name == FORBIDDEN_MODULE or module_name.startswith(
                f"{FORBIDDEN_MODULE}."
            ):
                violations.append(
                    f"{rel_path}:{node.lineno} application tests must use "
                    "application/domain/ports contracts instead of "
                    f"{module_name}"
                )
    return violations


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
