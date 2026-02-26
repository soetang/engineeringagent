from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks import emit_result_envelope
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.feedback-no-truncation"

_FEEDBACK_RENDERER_PATH = Path("src/engineeringagent/prompts/renderer.py")
_REMEDIATION = (
    "remove truncation-by-slicing from feedback prompt injection; "
    "feedback must be bounded by contract caps and canonical re-serialization"
)


def _parse_module(
    project_root: Path, relative_path: Path
) -> tuple[ast.AST | None, list[str]]:
    file_path = project_root / relative_path
    if not file_path.exists() or not file_path.is_file():
        return None, [f"{relative_path}:1 missing feedback prompt renderer; {_REMEDIATION}"]

    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    except SyntaxError as exc:
        line = exc.lineno or 1
        return None, [
            f"{relative_path}:{line} could not parse renderer module; {_REMEDIATION}"
        ]

    return tree, []


def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _is_truncate_feedback_call(node: ast.Call) -> bool:
    func = node.func
    return (isinstance(func, ast.Name) and func.id == "_truncate_feedback") or (
        isinstance(func, ast.Attribute) and func.attr == "_truncate_feedback"
    )


def _feedback_injection_violations(
    renderer_tree: ast.AST,
    *,
    relative_path: Path,
) -> list[str]:
    inject_node = _find_function(renderer_tree, "inject_feedback")
    if inject_node is None:
        return [
            f"{relative_path}:1 missing inject_feedback implementation; {_REMEDIATION}"
        ]

    violations: list[str] = []
    for node in ast.walk(inject_node):
        if isinstance(node, ast.Call) and _is_truncate_feedback_call(node):
            violations.append(
                f"{relative_path}:{node.lineno} feedback injection calls "
                f"_truncate_feedback; {_REMEDIATION}"
            )

        if not isinstance(node, ast.Subscript) or not isinstance(node.slice, ast.Slice):
            continue

        value = node.value
        if isinstance(value, ast.Name) and value.id == "feedback":
            violations.append(
                f"{relative_path}:{node.lineno} feedback injection slices "
                f"feedback; {_REMEDIATION}"
            )
            continue

        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "_normalize_feedback"
        ):
            violations.append(
                f"{relative_path}:{node.lineno} feedback injection slices "
                f"normalized feedback; {_REMEDIATION}"
            )

    return sorted(violations)


def main() -> int:
    """Run the feedback no-truncation fitness rule."""
    tree, violations = _parse_module(Path("."), _FEEDBACK_RENDERER_PATH)
    if tree is not None:
        violations.extend(
            _feedback_injection_violations(tree, relative_path=_FEEDBACK_RENDERER_PATH)
        )

    violations = sorted(violations)
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Feedback injection does not truncate by slicing."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} feedback injection truncation violation(s)."
    )

    emit_result_envelope(
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
