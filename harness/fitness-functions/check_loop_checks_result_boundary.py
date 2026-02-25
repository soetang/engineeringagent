from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks import emit_result_envelope
from engineeringagent.checks.fitness.boundary_reporting import (
    build_boundary_rule_result,
)
from engineeringagent.checks.fitness.scope_traversal import (
    collect_node_violations,
    collect_loop_boundary_rule_violations,
    sorted_violation_messages,
)


RULE_ID = "architecture.loop-checks-result-boundary"

_BANNED_CHECKS_RESULT_ATTRIBUTES = {
    "failed_group",
    "failed_payload",
    "decisions",
    "executions",
}
_BANNED_CHECKS_PAYLOAD_KEYS = {
    "check_type",
    "decision",
    "reason",
    "payload",
}
_CHECKS_RESULT_ATTRIBUTE_BASES = {
    "failed_payload",
    "decisions",
    "executions",
}
_CHECKS_RESULT_NAME_BASES = {
    "failure_result",
    "last_result",
    "result",
}
_REMEDIATION = (
    "remove loop-side checks-internal branching/parsing; loop may consume only "
    "checks run result fields ok/output/prompt_feedback"
)


def _is_checks_result_payload_base(node: ast.expr) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr in _CHECKS_RESULT_ATTRIBUTE_BASES
    if isinstance(node, ast.Name):
        return node.id in _CHECKS_RESULT_NAME_BASES
    if isinstance(node, ast.Subscript):
        return _is_checks_result_payload_base(node.value)
    return False


def _checks_boundary_violations(relative: Path, tree: ast.AST) -> list[str]:
    def _attribute_violation(node: ast.Attribute) -> str | None:
        if (
            node.attr not in _BANNED_CHECKS_RESULT_ATTRIBUTES
            or not _is_checks_result_payload_base(node.value)
        ):
            return None
        return (
            f"{relative}:{node.lineno} accesses checks result field "
            f"'{node.attr}' inside loop boundary; {_REMEDIATION}"
        )

    def _subscript_violation(node: ast.Subscript) -> str | None:
        key_value: str | None = None
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            key_value = node.slice.value
        if (
            key_value is None
            or key_value not in _BANNED_CHECKS_PAYLOAD_KEYS
            or not _is_checks_result_payload_base(node.value)
        ):
            return None
        return (
            f"{relative}:{node.lineno} parses checks payload key '{key_value}' "
            f"inside loop boundary; {_REMEDIATION}"
        )

    violations = collect_node_violations(
        tree,
        node_type=ast.Attribute,
        violation_for_node=_attribute_violation,
    )
    violations.extend(
        collect_node_violations(
            tree,
            node_type=ast.Subscript,
            violation_for_node=_subscript_violation,
        )
    )

    return sorted_violation_messages(violations)


def _loop_checks_result_boundary_violations(project_root: Path) -> list[str]:
    return collect_loop_boundary_rule_violations(
        project_root,
        include_prompt_renderer=False,
        remediation=_REMEDIATION,
        module_violations=_checks_boundary_violations,
    )


def main() -> int:
    """Run loop-checks result-boundary fitness rule."""
    violations = _loop_checks_result_boundary_violations(Path("."))
    emit_result_envelope(
        build_boundary_rule_result(
            rule_id=RULE_ID,
            violations=violations,
            pass_summary="Loop/checks result-boundary constraints satisfied.",
            fail_summary_label="loop/checks boundary",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
