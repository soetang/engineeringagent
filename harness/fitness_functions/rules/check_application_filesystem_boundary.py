from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.adapters.quality.fitness import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.application-filesystem-boundary"
PROJECT_ROOT = Path(".")
APPLICATION_ROOT = PROJECT_ROOT / "src" / "engineeringagent" / "application"
_MUTATING_PATH_METHODS = frozenset(
    {
        "mkdir",
        "open",
        "rename",
        "replace",
        "touch",
        "unlink",
        "write_bytes",
        "write_text",
    }
)


def _iter_application_modules(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(sorted(path for path in root.rglob("*.py") if path.is_file()))


def _scan_file(path: Path) -> list[str]:
    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{rel_path}: failed to read application module: {exc}"]

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        detail = str(exc.msg).strip() or "invalid syntax"
        return [f"{rel_path}:{exc.lineno or 1} failed to parse: {detail}"]

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _MUTATING_PATH_METHODS:
            continue
        violations.append(
            f"{rel_path}:{node.lineno} application modules must delegate filesystem "
            f"mutations through ports or injected dependencies; found `{node.func.attr}()`"
        )
    return violations


def _application_filesystem_violations(project_root: Path) -> list[str]:
    violations: list[str] = []
    for path in _iter_application_modules(
        project_root / "src" / "engineeringagent" / "application"
    ):
        violations.extend(_scan_file(path))
    return sorted(set(violations))


def main() -> int:
    """Run the application-filesystem-boundary fitness rule."""
    violations = _application_filesystem_violations(PROJECT_ROOT)
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Application modules avoid direct filesystem mutations."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} application filesystem-boundary violation(s)."
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
