from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.boundary_reporting import (
    build_boundary_rule_result,
)
from engineeringagent.adapters.quality.fitness.scope_traversal import (
    call_symbol,
    collect_loop_boundary_rule_violations,
    collect_node_violations,
    sorted_violation_messages,
)


RULE_ID = "architecture.loop-checks-policy-ownership"

_CHECK_GROUP_LITERALS = frozenset({"validate", "commands", "fitness", "reviewers"})
_POLICY_KEYWORDS = frozenset({"checks", "selection_profile"})
_REMEDIATION = (
    "remove loop-owned checks selection policy and call run_checks with phase-only "
    "context; checks owns timing/group decisions"
)


def _extract_group_literals(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value.strip()
        return {value} if value in _CHECK_GROUP_LITERALS else set()
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        extracted: set[str] = set()
        for element in node.elts:
            extracted.update(_extract_group_literals(element))
        return extracted
    if isinstance(node, ast.Dict):
        extracted: set[str] = set()
        for key in node.keys:
            if key is not None:
                extracted.update(_extract_group_literals(key))
        for value in node.values:
            extracted.update(_extract_group_literals(value))
        return extracted
    return set()


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in target.elts:
            names.extend(_target_names(elt))
        return names
    return []


def _is_policy_target(name: str) -> bool:
    normalized = name.upper()
    if "CHECK_GROUP" in normalized:
        return True
    if "GROUPS_BY_PHASE" in normalized:
        return True
    return "GROUP" in normalized and "CHECK" in normalized


def _assignment_policy_violations(relative: Path, tree: ast.AST) -> list[tuple[int, str]]:
    def _violation_for_assign(node: ast.Assign) -> str | None:
        group_literals = sorted(_extract_group_literals(node.value))
        if not group_literals:
            return None
        target_names = {
            name for target in node.targets for name in _target_names(target)
        }
        policy_targets = sorted(name for name in target_names if _is_policy_target(name))
        if not policy_targets:
            return None
        return (
            f"{relative}:{node.lineno} defines loop-owned checks group policy "
            f"{policy_targets} with group literals {group_literals}; {_REMEDIATION}"
        )

    def _violation_for_ann_assign(node: ast.AnnAssign) -> str | None:
        if node.value is None:
            return None
        group_literals = sorted(_extract_group_literals(node.value))
        if not group_literals:
            return None
        target_names = _target_names(node.target)
        policy_targets = sorted(name for name in target_names if _is_policy_target(name))
        if not policy_targets:
            return None
        return (
            f"{relative}:{node.lineno} defines loop-owned checks group policy "
            f"{policy_targets} with group literals {group_literals}; {_REMEDIATION}"
        )

    violations = collect_node_violations(
        tree,
        node_type=ast.Assign,
        violation_for_node=_violation_for_assign,
    )
    violations.extend(
        collect_node_violations(
            tree,
            node_type=ast.AnnAssign,
            violation_for_node=_violation_for_ann_assign,
        )
    )
    return violations


def _run_checks_policy_violations(relative: Path, tree: ast.AST) -> list[tuple[int, str]]:
    def _violation_for_call(node: ast.Call) -> list[str] | None:
        if call_symbol(node) != "run_checks":
            return None

        messages: list[str] = []
        for keyword in node.keywords:
            if keyword.arg not in _POLICY_KEYWORDS:
                continue
            if keyword.arg == "checks":
                explicit_groups = sorted(_extract_group_literals(keyword.value))
                group_suffix = (
                    f" with explicit groups {explicit_groups}"
                    if explicit_groups
                    else ""
                )
                messages.append(
                    f"{relative}:{node.lineno} passes explicit checks policy to "
                    f"run_checks{group_suffix}; {_REMEDIATION}"
                )
                continue
            profile_value = "<non-literal>"
            if isinstance(keyword.value, ast.Constant) and isinstance(
                keyword.value.value,
                str,
            ):
                profile_value = repr(keyword.value.value)
            messages.append(
                f"{relative}:{node.lineno} passes selection profile "
                f"'{keyword.arg}={profile_value}' to run_checks; {_REMEDIATION}"
            )
        return messages or None

    return collect_node_violations(
        tree,
        node_type=ast.Call,
        violation_for_node=_violation_for_call,
    )


def _module_violations(relative: Path, tree: ast.AST) -> list[str]:
    violations: list[tuple[int, str]] = []
    violations.extend(_assignment_policy_violations(relative, tree))
    violations.extend(_run_checks_policy_violations(relative, tree))
    return sorted_violation_messages(violations)


def _loop_checks_policy_ownership_violations(project_root: Path) -> list[str]:
    return collect_loop_boundary_rule_violations(
        project_root,
        include_prompt_renderer=False,
        remediation=_REMEDIATION,
        module_violations=_module_violations,
    )


def main() -> int:
    """Run loop-checks policy ownership fitness rule."""
    violations = _loop_checks_policy_ownership_violations(Path("."))
    emit_fitness_result(
        build_boundary_rule_result(
            rule_id=RULE_ID,
            violations=violations,
            pass_summary="Loop/checks policy-ownership boundary satisfied.",
            fail_summary_label="loop/checks policy ownership boundary",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
