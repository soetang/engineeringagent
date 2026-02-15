from __future__ import annotations

import ast
from pathlib import Path

from result_envelope import emit_result_envelope


RULE_ID = "architecture.loop-subprocess-boundary"
_SOURCE_PACKAGE_ROOT = Path("src/engineeringagent")
_BLOCKED_SUBPROCESS_CALLS = {
    "run",
    "Popen",
    "call",
    "check_call",
    "check_output",
}
_SUBPROCESS_ALLOWLIST_MODULES = (
    "engineeringagent.commit_messages",
    "engineeringagent.fitness.adapters",
    "engineeringagent.gates",
    "engineeringagent.git.client",
    "engineeringagent.opencode.client",
)
_SUBPROCESS_ALLOWLIST = {
    _SOURCE_PACKAGE_ROOT
    / f"{module.removeprefix('engineeringagent.').replace('.', '/')}.py"
    for module in _SUBPROCESS_ALLOWLIST_MODULES
}


def _collect_subprocess_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    module_aliases: set[str] = set()
    imported_call_aliases: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "subprocess":
                    continue
                module_aliases.add(alias.asname or alias.name)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0 or node.module != "subprocess":
            continue
        for alias in node.names:
            if alias.name not in _BLOCKED_SUBPROCESS_CALLS:
                continue
            imported_call_aliases.add(alias.asname or alias.name)

    return module_aliases, imported_call_aliases


def _subprocess_call_violation(
    node: ast.Call,
    *,
    relative: Path,
    module_aliases: set[str],
    imported_call_aliases: set[str],
) -> str | None:
    func = node.func

    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in module_aliases
        and func.attr in _BLOCKED_SUBPROCESS_CALLS
    ):
        return (
            f"{relative}:{node.lineno} uses {func.value.id}.{func.attr}; move this "
            "command call to an approved client/adapter module"
        )

    if isinstance(func, ast.Name) and func.id in imported_call_aliases:
        return (
            f"{relative}:{node.lineno} uses {func.id}(...) from subprocess; move "
            "this command call to an approved client/adapter module"
        )

    return None


def _subprocess_call_violations(file_path: Path, project_root: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    relative = file_path.relative_to(project_root)
    module_aliases, imported_call_aliases = _collect_subprocess_aliases(tree)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        violation = _subprocess_call_violation(
            node,
            relative=relative,
            module_aliases=module_aliases,
            imported_call_aliases=imported_call_aliases,
        )
        if violation is not None:
            violations.append(violation)

    return violations


def _loop_subprocess_boundary_violations(project_root: Path) -> list[str]:
    violations: list[str] = []
    source_root = project_root / _SOURCE_PACKAGE_ROOT

    if not source_root.exists():
        violations.append(f"missing source package root: {_SOURCE_PACKAGE_ROOT}")
        return violations

    for file_path in sorted(source_root.rglob("*.py")):
        relative = file_path.relative_to(project_root)
        if relative in _SUBPROCESS_ALLOWLIST:
            continue
        violations.extend(_subprocess_call_violations(file_path, project_root))

    return sorted(violations)


def main() -> int:
    violations = _loop_subprocess_boundary_violations(Path("."))
    status = "pass" if not violations else "fail"
    summary = (
        "Subprocess boundary allowlist constraints satisfied."
        if status == "pass"
        else (
            "Detected "
            f"{len(violations)} subprocess invocation(s) outside allowlisted modules."
        )
    )

    emit_result_envelope(
        rule_id=RULE_ID,
        status=status,
        severity="error",
        summary=summary,
        violations=violations,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
