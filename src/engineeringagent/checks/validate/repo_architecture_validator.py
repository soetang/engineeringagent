from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks.validate.contracts import ValidationContext, ValidationIssue


class RepoArchitectureValidator:
    """Repo-owned validator for architecture-level static contracts."""

    validator_id = "repo.architecture"

    def validate(self, *, context: ValidationContext) -> tuple[ValidationIssue, ...]:
        """Return deterministic architecture issues for repository-owned layers."""

        ports_root = context.project_root / "src" / "engineeringagent" / "ports"
        issues: list[ValidationIssue] = []
        for module_path in sorted(ports_root.glob("*.py")):
            if module_path.name == "__init__.py":
                continue
            issues.extend(_port_protocol_issues(module_path, project_root=context.project_root))
        return tuple(issues)


def _port_protocol_issues(
    module_path: Path,
    *,
    project_root: Path,
) -> tuple[ValidationIssue, ...]:
    rel_path = module_path.relative_to(project_root).as_posix()
    module = _parse_module(module_path, rel_path=rel_path)
    if isinstance(module, ValidationIssue):
        return (module,)
    if _module_declares_protocol(module):
        return ()
    return (
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path=rel_path,
            message="ports modules must declare at least one Protocol contract",
            code="repo.architecture.ports-protocol-contract",
        ),
    )


def _parse_module(module_path: Path, *, rel_path: str) -> ast.Module | ValidationIssue:
    try:
        source = module_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path=rel_path,
            message=f"failed to read ports module: {exc}",
            code="repo.architecture.read-failure",
        )
    try:
        return ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        detail = str(exc.msg).strip() or "invalid syntax"
        return ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path=rel_path,
            message=f"failed to parse ports module: {detail}",
            code="repo.architecture.parse-failure",
        )


def _module_declares_protocol(module: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ClassDef) and any(_is_protocol_base(base) for base in node.bases)
        for node in module.body
    )


def _is_protocol_base(base: ast.expr) -> bool:
    if isinstance(base, ast.Name):
        return base.id == "Protocol"
    if isinstance(base, ast.Attribute):
        return base.attr == "Protocol"
    return False
