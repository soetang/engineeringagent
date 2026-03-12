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


RULE_ID = "architecture.bootstrap-runtime-surface"
PROJECT_ROOT = Path(".")
BOOTSTRAP_INIT = PROJECT_ROOT / "src" / "engineeringagent" / "bootstrap" / "__init__.py"
FORBIDDEN_EXPORTS = {
    "LoopRun",
    "RunConfig",
    "RunConfigOptions",
    "RunServices",
    "RunState",
    "build_loop_run",
    "build_run_config",
    "enforce_worktree_precondition",
    "run_selected_feature_iterations",
    "run_loop_controller",
}
FORBIDDEN_IMPORT_TARGET = "engineeringagent.adapters.runtime"
REMEDIATION = (
    "bootstrap package exports must stay bootstrap-owned; call adapter runtime "
    "helpers from the adapter package directly instead of proxying them through "
    "engineeringagent.bootstrap."
)


def _load_tree(path: Path) -> ast.AST:
    source = path.read_text(encoding="utf-8")
    return ast.parse(source, filename=path.as_posix())


def _string_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _collect_violations(project_root: Path) -> list[str]:
    path = project_root / BOOTSTRAP_INIT.relative_to(PROJECT_ROOT)
    if not path.is_file():
        return [f"{BOOTSTRAP_INIT.as_posix()}: missing bootstrap package module"]

    try:
        tree = _load_tree(path)
    except (OSError, SyntaxError) as exc:
        return [f"{BOOTSTRAP_INIT.as_posix()}: failed to inspect bootstrap exports: {exc}"]

    violations: list[str] = []
    rel_path = path.relative_to(project_root).as_posix()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == FORBIDDEN_IMPORT_TARGET:
            violations.append(
                f"{rel_path}:{node.lineno} bootstrap package must not import "
                f"{FORBIDDEN_IMPORT_TARGET!r}; {REMEDIATION}"
            )
            continue

        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "import_module"
                and node.args
                and _string_literal(node.args[0]) == FORBIDDEN_IMPORT_TARGET
            ):
                violations.append(
                    f"{rel_path}:{node.lineno} bootstrap package must not proxy "
                    f"{FORBIDDEN_IMPORT_TARGET!r}; {REMEDIATION}"
                )
                continue

        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id != "__all__":
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
            continue
        for element in node.value.elts:
            export_name = _string_literal(element)
            if export_name in FORBIDDEN_EXPORTS:
                violations.append(
                    f"{rel_path}:{getattr(element, 'lineno', node.lineno)} bootstrap "
                    f"package must not re-export {export_name!r}; {REMEDIATION}"
                )

    return sorted(set(violations))


def main() -> int:
    """Run the bootstrap runtime surface fitness rule."""
    violations = _collect_violations(PROJECT_ROOT)
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Bootstrap package exports stay bootstrap-owned."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} bootstrap runtime surface violation(s)."
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
