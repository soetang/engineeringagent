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


RULE_ID = "architecture.progress-log-path-locality"

_SOURCE_PACKAGE_ROOT = Path("src/engineeringagent")

_APPROVED_PATH_LITERAL_FILES = {
    _SOURCE_PACKAGE_ROOT / "progress" / "paths.py",
}

_PROGRESS_PATH_LITERAL_TOKENS = (
    "progress/runs/runs.jsonl",
    "progress/runs.jsonl",
    "progress/reviewers/state.json",
    "reviewers-state.json",
    "/run.txt",
    "/handoff.md",
    "progress/features/",
    "run-feature-",
)

_LOOP_LOG_SINK_HELPERS = {
    "runs_jsonl_path",
    "run_feature_log_path",
    "handoff_markdown_path",
}

_PATH_HELPER_REMEDIATION = (
    "construct progress artifact paths via engineeringagent.progress.paths.* and "
    "write loop log sinks via engineeringagent.progress.logging.*"
)


def _iter_literal_string_segments(tree: ast.AST) -> list[tuple[int, str]]:
    segments: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            line = getattr(node, "lineno", 1)
            segments.append((line, node.value))
            continue
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    line = getattr(value, "lineno", getattr(node, "lineno", 1))
                    segments.append((line, value.value))
    return segments


def _matches_progress_path_literal(segment: str) -> str | None:
    for token in _PROGRESS_PATH_LITERAL_TOKENS:
        if token in segment:
            return token
    return None


def _progress_path_literal_violations(
    *,
    file_path: Path,
    project_root: Path,
    tree: ast.AST,
) -> list[str]:
    relative = file_path.relative_to(project_root)
    if relative in _APPROVED_PATH_LITERAL_FILES:
        return []

    violations: list[str] = []
    for line, segment in _iter_literal_string_segments(tree):
        token = _matches_progress_path_literal(segment)
        if not token:
            continue
        violations.append(
            f"{relative}:{line} contains progress artifact path literal '{token}' "
            f"outside engineeringagent.progress.paths; {_PATH_HELPER_REMEDIATION}"
        )
    return violations


def _call_helper_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _assigned_loop_log_sink_names(tree: ast.AST) -> set[str]:
    sink_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = node.value
            if not isinstance(value, ast.Call):
                continue
            helper = _call_helper_name(value)
            if helper not in _LOOP_LOG_SINK_HELPERS:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    sink_names.add(target.id)
        if isinstance(node, ast.AnnAssign):
            value = node.value
            if not isinstance(value, ast.Call):
                continue
            helper = _call_helper_name(value)
            if helper not in _LOOP_LOG_SINK_HELPERS:
                continue
            if isinstance(node.target, ast.Name):
                sink_names.add(node.target.id)
    return sink_names


def _string_literals_from_node(node: ast.AST) -> list[str]:
    values: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.append(child.value)
    return values


def _expr_targets_loop_log_sink(expr: ast.AST, *, sink_names: set[str]) -> bool:
    if isinstance(expr, ast.Name) and expr.id in sink_names:
        return True
    if isinstance(expr, ast.Call):
        helper = _call_helper_name(expr)
        if helper in _LOOP_LOG_SINK_HELPERS:
            return True

    for value in _string_literals_from_node(expr):
        if _matches_progress_path_literal(value):
            return True
    return False


def _mode_from_call(call: ast.Call, *, mode_positional_index: int) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            if isinstance(keyword.value.value, str):
                return keyword.value.value
    if len(call.args) > mode_positional_index:
        constant = call.args[mode_positional_index]
        if isinstance(constant, ast.Constant) and isinstance(constant.value, str):
            return constant.value
    return None


def _mode_is_write(mode: str | None) -> bool:
    if mode is None:
        return False
    return any(flag in mode for flag in ("a", "w", "x", "+"))


def _call_is_builtin_open(call: ast.Call) -> bool:
    return isinstance(call.func, ast.Name) and call.func.id == "open"


def _builtin_open_target_expr(call: ast.Call) -> ast.AST | None:
    if call.args:
        return call.args[0]
    for keyword in call.keywords:
        if keyword.arg == "file":
            return keyword.value
    return None


def _direct_write_violations(
    *,
    file_path: Path,
    project_root: Path,
    tree: ast.AST,
) -> list[str]:
    relative = file_path.relative_to(project_root)
    sink_names = _assigned_loop_log_sink_names(tree)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if _call_is_builtin_open(node) and _mode_is_write(
            _mode_from_call(node, mode_positional_index=1)
        ):
            target = _builtin_open_target_expr(node)
            if target is not None and _expr_targets_loop_log_sink(
                target, sink_names=sink_names
            ):
                violations.append(
                    f"{relative}:{node.lineno} writes to loop log sink via direct "
                    f"file I/O (open); {_PATH_HELPER_REMEDIATION}"
                )
            continue

        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "open":
            if _mode_is_write(_mode_from_call(node, mode_positional_index=0)) and (
                _expr_targets_loop_log_sink(func.value, sink_names=sink_names)
            ):
                violations.append(
                    f"{relative}:{node.lineno} writes to loop log sink via direct "
                    f"file I/O (.open); {_PATH_HELPER_REMEDIATION}"
                )
            continue

        if isinstance(func, ast.Attribute) and func.attr in {
            "write_text",
            "write_bytes",
        }:
            if _expr_targets_loop_log_sink(func.value, sink_names=sink_names):
                violations.append(
                    f"{relative}:{node.lineno} writes to loop log sink via direct "
                    f"file I/O (.{func.attr}); {_PATH_HELPER_REMEDIATION}"
                )

    return violations


def _progress_log_locality_violations(project_root: Path) -> list[str]:
    source_root = project_root / _SOURCE_PACKAGE_ROOT
    if not source_root.exists():
        return [
            f"{_SOURCE_PACKAGE_ROOT}:1 missing source package root; {_PATH_HELPER_REMEDIATION}"
        ]

    violations: list[str] = []
    for file_path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        violations.extend(
            _progress_path_literal_violations(
                file_path=file_path,
                project_root=project_root,
                tree=tree,
            )
        )
        violations.extend(
            _direct_write_violations(
                file_path=file_path,
                project_root=project_root,
                tree=tree,
            )
        )

    return sorted(violations)


def main() -> int:
    """Run the progress-log locality fitness rule."""
    violations = _progress_log_locality_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Progress log path locality constraints satisfied."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} progress log locality violation(s)."
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
