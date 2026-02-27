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


RULE_ID = "architecture.no-facade-varargs-shims"
SOURCE_ROOT = Path("src/engineeringagent")
REMEDIATION = (
    "replace facade varargs/signature shims with explicit typed contracts "
    "(for example LoopRun/RunConfig/RunServices/RunState) and avoid hidden kwargs "
    "dropping without an explicit typed field"
)

_ALLOWED_VARARG_FUNCTIONS = {
    ("src/engineeringagent/loop_runtime/facade_signatures.py", "bind_facade_call"),
}

_ALLOWED_SIGNATURE_ASSIGNMENTS: set[tuple[str, str]] = set()

_ALLOWED_HIDDEN_KWARG_DROPS: set[tuple[str, str, str]] = set()


def _is_loop_orchestration_module(rel_path: str) -> bool:
    return rel_path == "src/engineeringagent/loop.py" or rel_path.startswith(
        "src/engineeringagent/loop_runtime/"
    )


def _vararg_kind_text(node: ast.arguments) -> str:
    kinds: list[str] = []
    if node.vararg is not None:
        kinds.append(f"*{node.vararg.arg}")
    if node.kwarg is not None:
        kinds.append(f"**{node.kwarg.arg}")
    return " and ".join(kinds)


def _iter_python_files(source_root: Path) -> list[Path]:
    if not source_root.is_dir():
        return []
    return sorted(source_root.rglob("*.py"))


def _relative_path(file_path: Path, project_root: Path) -> str:
    return file_path.relative_to(project_root).as_posix()


def _string_argument(call: ast.Call, position: int) -> str | None:
    if len(call.args) > position:
        candidate = call.args[position]
        if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
            return candidate.value
    return None


def _string_keyword_argument(call: ast.Call, keyword: str) -> str | None:
    for entry in call.keywords:
        if entry.arg != keyword:
            continue
        if isinstance(entry.value, ast.Constant) and isinstance(entry.value.value, str):
            return entry.value.value
    return None


def _name_argument(call: ast.Call, position: int, keyword: str) -> str | None:
    if len(call.args) > position:
        candidate = call.args[position]
        if isinstance(candidate, ast.Name):
            return candidate.id

    for entry in call.keywords:
        if entry.arg != keyword:
            continue
        if isinstance(entry.value, ast.Name):
            return entry.value.id
    return None


def _owner_name(target: ast.Attribute) -> str | None:
    if isinstance(target.value, ast.Name):
        return target.value.id
    return None


def _collect_vararg_violations(tree: ast.AST, rel_path: str) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.args.vararg is None and node.args.kwarg is None:
            continue
        if (rel_path, node.name) in _ALLOWED_VARARG_FUNCTIONS:
            continue
        violations.append(
            (
                f"{rel_path}:{node.lineno} function '{node.name}' uses "
                f"{_vararg_kind_text(node.args)} facade parameters; {REMEDIATION}"
            )
        )
    return violations


def _collect_signature_assignment_violations(tree: ast.AST, rel_path: str) -> list[str]:
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        targets: list[ast.expr]
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        else:
            targets = [node.target]

        for target in targets:
            if not isinstance(target, ast.Attribute) or target.attr != "__signature__":
                continue
            owner = _owner_name(target)
            if (
                owner is not None
                and (rel_path, owner) in _ALLOWED_SIGNATURE_ASSIGNMENTS
            ):
                continue
            owner_label = owner if owner is not None else "<non-name-target>"
            violations.append(
                (
                    f"{rel_path}:{getattr(target, 'lineno', 1)} assigns "
                    f"`{owner_label}.__signature__`; {REMEDIATION}"
                )
            )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "setattr":
            continue

        signature_name = _string_argument(node, 1) or _string_keyword_argument(
            node, "name"
        )
        if signature_name != "__signature__":
            continue

        owner = _name_argument(node, 0, "object")
        if owner is not None and (rel_path, owner) in _ALLOWED_SIGNATURE_ASSIGNMENTS:
            continue
        owner_label = owner if owner is not None else "<non-name-target>"
        violations.append(
            (
                f"{rel_path}:{getattr(node, 'lineno', 1)} calls "
                f"setattr({owner_label}, '__signature__', ...); {REMEDIATION}"
            )
        )
    return violations


def _collect_hidden_kwarg_drop_violations(tree: ast.AST, rel_path: str) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        kwargs_name = node.args.kwarg.arg if node.args.kwarg is not None else None
        if kwargs_name is None:
            continue

        for descendant in ast.walk(node):
            if not isinstance(descendant, ast.Call):
                continue
            if not isinstance(descendant.func, ast.Attribute):
                continue
            if descendant.func.attr != "pop":
                continue
            if not isinstance(descendant.func.value, ast.Name):
                continue
            if descendant.func.value.id != kwargs_name:
                continue

            dropped_key = _string_argument(descendant, 0)
            allowlist_key = dropped_key if dropped_key is not None else "<non-string>"
            if (rel_path, node.name, allowlist_key) in _ALLOWED_HIDDEN_KWARG_DROPS:
                continue
            key_label = dropped_key if dropped_key is not None else "<non-string>"
            violations.append(
                (
                    f"{rel_path}:{getattr(descendant, 'lineno', 1)} function "
                    f"'{node.name}' drops hidden kwarg key '{key_label}' via "
                    f"`{kwargs_name}.pop(...)`; {REMEDIATION}"
                )
            )
    return violations


def _collect_violations(project_root: Path) -> list[str]:
    source_root = project_root / SOURCE_ROOT
    if not source_root.is_dir():
        return [
            f"{SOURCE_ROOT.as_posix()}:1 missing source package root; {REMEDIATION}"
        ]

    violations: list[str] = []
    for file_path in _iter_python_files(source_root):
        text = file_path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(file_path))
        rel_path = _relative_path(file_path, project_root)
        if not _is_loop_orchestration_module(rel_path):
            continue
        violations.extend(_collect_vararg_violations(tree, rel_path))
        violations.extend(_collect_signature_assignment_violations(tree, rel_path))
        violations.extend(_collect_hidden_kwarg_drop_violations(tree, rel_path))
    return sorted(violations)


def main() -> int:
    """Run the no-facade-varargs-shims fitness rule."""
    violations = _collect_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "No facade varargs shims, signature masking, or hidden kwargs dropping detected."
        if status == RuleStatus.PASS
        else (
            "Detected facade varargs shim/signature-masking/hidden-kwargs-drop "
            "regression patterns."
        )
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
