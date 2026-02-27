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


RULE_ID = "architecture.dep-directionality"

_DISALLOWED_IMPORTS: dict[str, tuple[str, ...]] = {
    "engineeringagent.specs": (
        "engineeringagent.cli",
        "engineeringagent.loop",
        "engineeringagent.loop_runtime",
        "engineeringagent.checks.validate.validator",
    ),
    "engineeringagent.checks.validate.validator": (
        "engineeringagent.cli",
        "engineeringagent.loop",
        "engineeringagent.loop_runtime",
    ),
    "engineeringagent.cli": ("engineeringagent.loop_runtime",),
    "engineeringagent.loop": ("engineeringagent.cli",),
}


def _module_path(project_root: Path, module_name: str) -> Path:
    _, _, suffix = module_name.partition("engineeringagent.")
    return project_root / "src" / "engineeringagent" / f"{suffix.replace('.', '/')}.py"


def _resolve_import_from_base(module_name: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    module_parts = module_name.split(".")
    if node.level > len(module_parts):
        return None

    base_parts = module_parts[: -node.level]
    if node.module:
        base_parts.extend(node.module.split("."))
    if not base_parts:
        return None
    return ".".join(base_parts)


def _collect_imports(path: Path, module_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from_base(module_name, node)
            if base is None:
                continue
            imports.add(base)
            for alias in node.names:
                imports.add(f"{base}.{alias.name}")
    return imports


def _directionality_violations(project_root: Path) -> list[str]:
    violations: list[str] = []
    for module_name, blocked_modules in sorted(_DISALLOWED_IMPORTS.items()):
        module_path = _module_path(project_root, module_name)
        if not module_path.exists():
            violations.append(f"missing module for directionality check: {module_name}")
            continue

        for imported in sorted(_collect_imports(module_path, module_name)):
            for blocked in blocked_modules:
                if imported == blocked or imported.startswith(f"{blocked}."):
                    violations.append(
                        f"{module_name} imports blocked dependency {imported}"
                    )
    return sorted(violations)


def main() -> int:
    """Run the dependency directionality fitness rule."""
    violations = _directionality_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Dependency directionality constraints satisfied."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} dependency directionality violation(s)."
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
