from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks.fitness.local_support_loader import load_local_support_module


_SUPPORT_MODULE = load_local_support_module(
    "policy_rule_support",
    caller_file=Path(__file__),
)
load_yaml_policy = _SUPPORT_MODULE.load_yaml_policy
run_policy_rule = _SUPPORT_MODULE.run_policy_rule


RULE_ID = "architecture.module-statement-budget"
_DEFAULT_POLICY = (
    Path(__file__).resolve().parent.parent
    / "policies"
    / "module_statement_budget_policy.yaml"
)


def _load_policy(config_file: Path) -> list[tuple[Path, int]]:
    payload = load_yaml_policy(config_file)
    budgets = payload.get("budgets")
    if not isinstance(budgets, list) or not budgets:
        raise ValueError("policy field 'budgets' must be a non-empty list")

    normalized_budgets: list[tuple[Path, int]] = []
    seen_roots: set[Path] = set()
    for index, budget in enumerate(budgets):
        if not isinstance(budget, dict):
            raise ValueError(f"policy budgets[{index}] must be a mapping")

        root = budget.get("root")
        cap = budget.get("cap")
        if not isinstance(root, str) or not root:
            raise ValueError(
                f"policy budgets[{index}].root must be a non-empty string"
            )
        if not isinstance(cap, int) or cap <= 0:
            raise ValueError(f"policy budgets[{index}].cap must be a positive integer")

        root_path = Path(root)
        if root_path in seen_roots:
            raise ValueError(f"duplicate policy budget root: {root}")
        seen_roots.add(root_path)
        normalized_budgets.append((root_path, cap))

    return normalized_budgets


def _docstring_statement_node_ids(tree: ast.AST) -> set[int]:
    docstring_node_ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        if not node.body:
            continue

        first_statement = node.body[0]
        if not isinstance(first_statement, ast.Expr):
            continue

        value = first_statement.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            docstring_node_ids.add(id(first_statement))

    return docstring_node_ids


def count_non_doc_statements_in_file(path: Path) -> int:
    """Count AST statements in a Python file, excluding docstring-only expressions."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstring_node_ids = _docstring_statement_node_ids(tree)
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.stmt) and id(node) not in docstring_node_ids
    )


def _collect_python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _module_statement_budget_violations(
    project_root: Path, *, config_file: Path
) -> list[str]:
    violations: set[str] = set()
    for root, cap in _load_policy(config_file):
        scan_root = project_root / root
        for path in _collect_python_files(scan_root):
            relative_path = path.relative_to(project_root).as_posix()
            try:
                statement_count = count_non_doc_statements_in_file(path)
            except SyntaxError as exc:
                raise ValueError(
                    f"failed parsing Python module {relative_path}: {exc.msg} at line {exc.lineno}"
                ) from exc

            if statement_count > cap:
                violations.add(f"{relative_path}: statements={statement_count} cap={cap}")

    return sorted(violations)


def main() -> int:
    """Run the module statement budget fitness rule."""
    return run_policy_rule(
        rule_id=RULE_ID,
        default_policy=_DEFAULT_POLICY,
        pass_summary="Python modules satisfy configured statement budgets.",
        fail_summary=lambda count: (
            f"Detected {count} Python module(s) exceeding statement budgets."
        ),
        error_summary_prefix="Native statement-budget scan failed",
        evaluate=lambda project_root, config_file: _module_statement_budget_violations(
            project_root,
            config_file=config_file,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
