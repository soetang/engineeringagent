from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks.validate.contracts import ValidationContext, ValidationIssue


class RepoArchitectureValidator:
    """Repo-owned validator for architecture-level static contracts."""

    validator_id = "repo.architecture"

    def validate(self, *, context: ValidationContext) -> tuple[ValidationIssue, ...]:
        """Return deterministic architecture issues for repository-owned layers."""

        src_root = context.project_root / "src" / "engineeringagent"
        application_root = src_root / "application"
        domain_root = src_root / "domain"
        ports_root = context.project_root / "src" / "engineeringagent" / "ports"
        issues: list[ValidationIssue] = []
        issues.extend(_deleted_path_issues(project_root=context.project_root))
        issues.extend(
            _legacy_import_issues(
                project_root=context.project_root,
                modules=_iter_python_modules(src_root),
            )
        )
        for module_path in _iter_python_modules(domain_root):
            issues.extend(_domain_module_issues(module_path, project_root=context.project_root))
        for module_path in _iter_python_modules(application_root):
            issues.extend(
                _application_module_issues(module_path, project_root=context.project_root)
            )
        for module_path in sorted(ports_root.glob("*.py")):
            if module_path.name == "__init__.py":
                continue
            issues.extend(_port_protocol_issues(module_path, project_root=context.project_root))
        return _deduplicate_issues(issues)


def _port_protocol_issues(
    module_path: Path,
    *,
    project_root: Path,
) -> tuple[ValidationIssue, ...]:
    rel_path = module_path.relative_to(project_root).as_posix()
    module = _parse_module(module_path, rel_path=rel_path)
    if isinstance(module, ValidationIssue):
        return (module,)
    issues: list[ValidationIssue] = list(_application_import_issues(module, rel_path=rel_path))
    if not _module_declares_protocol(module):
        issues.append(
            ValidationIssue(
                validator_id="repo.architecture",
                scope="repo",
                path=rel_path,
                message="ports modules must declare at least one Protocol contract",
                code="repo.architecture.ports-protocol-contract",
            )
        )
    return tuple(issues)


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


def _iter_python_modules(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(path for path in root.rglob("*.py") if path.is_file() and path.name != "__init__.py")
    )


def _deduplicate_issues(issues: list[ValidationIssue]) -> tuple[ValidationIssue, ...]:
    unique: list[ValidationIssue] = []
    seen: set[tuple[str, str, str, str]] = set()
    for issue in issues:
        key = (issue.path, issue.code, issue.message, issue.validator_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return tuple(unique)


def _application_module_issues(
    module_path: Path,
    *,
    project_root: Path,
) -> tuple[ValidationIssue, ...]:
    rel_path = module_path.relative_to(project_root).as_posix()
    module = _parse_module(module_path, rel_path=rel_path)
    if isinstance(module, ValidationIssue):
        return (module,)

    issues: list[ValidationIssue] = []
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and any(_is_protocol_base(base) for base in node.bases):
            issues.append(
                ValidationIssue(
                    validator_id="repo.architecture",
                    scope="repo",
                    path=rel_path,
                    message="application modules must not declare Protocol contracts",
                    code="repo.architecture.application-protocol-contract",
                )
            )
            break

    issues.extend(
        _forbidden_import_issues(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.checks",),
            message="application modules must not import checks modules",
            code="repo.architecture.application-checks-import",
        )
    )
    issues.extend(
        _forbidden_import_issues(
            module,
            rel_path=rel_path,
            forbidden_modules=("engineeringagent.init_scaffold",),
            message="application and ports modules must not import init_scaffold modules",
            code="repo.architecture.init-scaffold-import",
        )
    )
    return tuple(issues)


def _domain_module_issues(
    module_path: Path,
    *,
    project_root: Path,
) -> tuple[ValidationIssue, ...]:
    rel_path = module_path.relative_to(project_root).as_posix()
    module = _parse_module(module_path, rel_path=rel_path)
    if isinstance(module, ValidationIssue):
        return (module,)

    return _forbidden_import_issues(
        module,
        rel_path=rel_path,
        forbidden_modules=(
            "engineeringagent.adapters",
            "engineeringagent.application",
            "engineeringagent.bootstrap",
            "engineeringagent.ports",
            "engineeringagent.presentation",
            "engineeringagent.specs",
        ),
        message=(
            "domain modules must not import application, ports, adapters, "
            "presentation, bootstrap, or legacy specs modules"
        ),
        code="repo.architecture.domain-import",
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


def _application_import_issues(
    module: ast.Module,
    *,
    rel_path: str,
) -> tuple[ValidationIssue, ...]:
    return _forbidden_import_issues(
        module,
        rel_path=rel_path,
        forbidden_modules=("engineeringagent.application",),
        message="ports modules must not import application modules",
        code="repo.architecture.ports-application-import",
    ) + _forbidden_import_issues(
        module,
        rel_path=rel_path,
        forbidden_modules=("engineeringagent.init_scaffold",),
        message="application and ports modules must not import init_scaffold modules",
        code="repo.architecture.init-scaffold-import",
    )


def _forbidden_import_issues(
    module: ast.Module,
    *,
    rel_path: str,
    forbidden_modules: tuple[str, ...],
    message: str,
    code: str,
) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    for node in ast.walk(module):
        imported_module: str | None = None
        if isinstance(node, ast.ImportFrom):
            imported_module = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _matches_forbidden_module(alias.name, forbidden_modules):
                    issues.append(
                        ValidationIssue(
                            validator_id="repo.architecture",
                            scope="repo",
                            path=rel_path,
                            message=message,
                            code=code,
                        )
                    )
            continue

        if imported_module is not None and _matches_forbidden_module(
            imported_module,
            forbidden_modules,
        ):
            issues.append(
                ValidationIssue(
                    validator_id="repo.architecture",
                    scope="repo",
                    path=rel_path,
                    message=message,
                    code=code,
                )
            )
    return tuple(issues)


def _matches_forbidden_module(module_name: str, forbidden_modules: tuple[str, ...]) -> bool:
    return any(
        module_name == forbidden_module or module_name.startswith(f"{forbidden_module}.")
        for forbidden_module in forbidden_modules
    )


def _legacy_import_issues(
    *,
    project_root: Path,
    modules: tuple[Path, ...],
) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    legacy_modules = (
        "engineeringagent.git",
        "engineeringagent.git.client",
        "engineeringagent.progress_paths",
        "engineeringagent.progress_logging",
    )
    legacy_members = {"git", "progress_paths", "progress_logging"}
    for module_path in modules:
        rel_path = module_path.relative_to(project_root).as_posix()
        module = _parse_module(module_path, rel_path=rel_path)
        if isinstance(module, ValidationIssue):
            issues.append(module)
            continue
        issues.extend(
            _legacy_import_issues_for_module(
                module,
                rel_path=rel_path,
                legacy_modules=legacy_modules,
                legacy_members=legacy_members,
            )
        )
    return tuple(issues)


def _legacy_import_issues_for_module(
    module: ast.Module,
    *,
    rel_path: str,
    legacy_modules: tuple[str, ...],
    legacy_members: set[str],
) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            issues.extend(
                _legacy_direct_import_issues(node, rel_path=rel_path, legacy_modules=legacy_modules)
            )
        if isinstance(node, ast.ImportFrom):
            issues.extend(
                _legacy_from_import_issues(
                    node,
                    rel_path=rel_path,
                    legacy_modules=legacy_modules,
                    legacy_members=legacy_members,
                )
            )
    return tuple(issues)


def _legacy_direct_import_issues(
    node: ast.Import,
    *,
    rel_path: str,
    legacy_modules: tuple[str, ...],
) -> tuple[ValidationIssue, ...]:
    return tuple(
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path=rel_path,
            message=f"production modules must not import deleted legacy module {alias.name}",
            code="repo.architecture.legacy-import",
        )
        for alias in node.names
        if alias.name in legacy_modules
    )


def _legacy_from_import_issues(
    node: ast.ImportFrom,
    *,
    rel_path: str,
    legacy_modules: tuple[str, ...],
    legacy_members: set[str],
) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    if node.module in legacy_modules:
        issues.append(
            ValidationIssue(
                validator_id="repo.architecture",
                scope="repo",
                path=rel_path,
                message=f"production modules must not import deleted legacy module {node.module}",
                code="repo.architecture.legacy-import",
            )
        )
    if node.module == "engineeringagent":
        issues.extend(
            ValidationIssue(
                validator_id="repo.architecture",
                scope="repo",
                path=rel_path,
                message=(
                    "production modules must not import deleted legacy member "
                    f"engineeringagent.{alias.name}"
                ),
                code="repo.architecture.legacy-import",
            )
            for alias in node.names
            if alias.name in legacy_members
        )
    return tuple(issues)


def _deleted_path_issues(*, project_root: Path) -> tuple[ValidationIssue, ...]:
    deleted_paths = tuple(
        sorted(
            (
        "src/engineeringagent/harness_checks_runtime.py",
        "src/engineeringagent/validator.py",
        "src/engineeringagent/ports/guidance_topics.py",
        "src/engineeringagent/ports/prompt_definitions.py",
        "src/engineeringagent/adapters/guidance/packaged_guidance_topics.py",
        "src/engineeringagent/adapters/prompts/bundled_prompt_definitions.py",
        "src/engineeringagent/adapters/prompts/filesystem_prompt_definitions.py",
        "src/engineeringagent/adapters/prompts/project_prompt_definitions.py",
        "src/engineeringagent/application/implementation_prompt.py",
        "src/engineeringagent/git/__init__.py",
        "src/engineeringagent/git/client.py",
        "src/engineeringagent/progress_paths.py",
        "src/engineeringagent/progress_logging.py",
            )
        )
    )
    issues = [
        ValidationIssue(
            validator_id="repo.architecture",
            scope="repo",
            path=relative_path,
            message="deleted legacy module path must remain absent",
            code="repo.architecture.deleted-path",
        )
        for relative_path in deleted_paths
        if (project_root / relative_path).exists()
    ]
    return tuple(issues)
