from __future__ import annotations

import ast
from pathlib import Path

from .contracts import CONTRACT_VERSION, RuleSeverity, RuleStatus

DEPENDENCY_DIRECTIONALITY_RULE_ID = "architecture.dep-directionality"
LOOP_SUBPROCESS_BOUNDARY_RULE_ID = "architecture.loop-subprocess-boundary"

_DISALLOWED_IMPORTS: dict[str, tuple[str, ...]] = {
    "engineeringagent.specs": (
        "engineeringagent.cli",
        "engineeringagent.loop",
        "engineeringagent.gates",
        "engineeringagent.validator",
    ),
    "engineeringagent.validator": (
        "engineeringagent.cli",
        "engineeringagent.loop",
    ),
    "engineeringagent.gates": (
        "engineeringagent.cli",
        "engineeringagent.loop",
    ),
    "engineeringagent.loop": ("engineeringagent.cli",),
}

_BLOCKED_SUBPROCESS_CALLS = {
    "run",
    "Popen",
    "call",
    "check_call",
    "check_output",
}
_SUBPROCESS_ALLOWLIST = {
    "src/engineeringagent/commit_messages.py",
    "src/engineeringagent/fitness/adapters.py",
    "src/engineeringagent/gates.py",
    "src/engineeringagent/git/client.py",
    "src/engineeringagent/opencode/client.py",
}
_SOURCE_PACKAGE_ROOT = Path("src/engineeringagent")


def evaluate_dependency_directionality(project_root: Path) -> dict[str, object]:
    """Evaluate import directionality constraints for core modules."""
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

    return {
        "contract_version": CONTRACT_VERSION,
        "rule_id": DEPENDENCY_DIRECTIONALITY_RULE_ID,
        "status": RuleStatus.PASS if not violations else RuleStatus.FAIL,
        "severity": RuleSeverity.ERROR,
        "summary": (
            "Dependency directionality constraints satisfied."
            if not violations
            else f"Detected {len(violations)} dependency directionality violation(s)."
        ),
        "violations": sorted(violations),
    }


def evaluate_loop_subprocess_boundary(project_root: Path) -> dict[str, object]:
    """Reject subprocess calls outside strict command-boundary allowlist."""
    violations: list[str] = []
    source_root = project_root / _SOURCE_PACKAGE_ROOT
    if not source_root.exists():
        violations.append(f"missing source package root: {_SOURCE_PACKAGE_ROOT}")
    else:
        for file_path in sorted(source_root.rglob("*.py")):
            relative = str(file_path.relative_to(project_root))
            if relative in _SUBPROCESS_ALLOWLIST:
                continue
            violations.extend(_subprocess_call_violations(file_path, project_root))

    return {
        "contract_version": CONTRACT_VERSION,
        "rule_id": LOOP_SUBPROCESS_BOUNDARY_RULE_ID,
        "status": RuleStatus.PASS if not violations else RuleStatus.FAIL,
        "severity": RuleSeverity.ERROR,
        "summary": (
            "Subprocess boundary allowlist constraints satisfied."
            if not violations
            else (
                "Detected "
                f"{len(violations)} subprocess invocation(s) outside allowlisted modules."
            )
        ),
        "violations": sorted(violations),
    }


def _module_path(project_root: Path, module_name: str) -> Path:
    _, _, suffix = module_name.partition("engineeringagent.")
    return project_root / "src" / "engineeringagent" / f"{suffix.replace('.', '/')}.py"


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


def _subprocess_call_violations(file_path: Path, project_root: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    relative = file_path.relative_to(project_root)
    violations: list[str] = []
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

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id in module_aliases
            and func.attr in _BLOCKED_SUBPROCESS_CALLS
        ):
            violations.append(
                f"{relative}:{node.lineno} uses {func.value.id}.{func.attr}; move this command call to an approved client/adapter module"
            )
            continue

        if isinstance(func, ast.Name) and func.id in imported_call_aliases:
            violations.append(
                f"{relative}:{node.lineno} uses {func.id}(...) from subprocess; move this command call to an approved client/adapter module"
            )
    return violations
