"""Helpers for parsing and classifying Python imports."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImportStatement:
    """Normalized import data for one parsed statement."""

    module: str
    line: int
    category: str


@dataclass(frozen=True)
class ModuleContext:
    """Resolved module metadata for a Python source file."""

    module_name: str
    package_name: str


def build_module_context(file_path: Path, repo_root: Path) -> ModuleContext:
    """Return the module and package names for a source file.

    Args:
        file_path: Absolute path to the Python file.
        repo_root: Absolute repository root path.

    Returns:
        Module metadata for the file.

    Raises:
        ValueError: If the file is not inside the repository source tree.
    """
    relative_path = file_path.resolve().relative_to(repo_root.resolve())
    if relative_path.suffix != ".py":
        raise ValueError(f"Expected a Python file, got: {relative_path}")

    parts = list(relative_path.with_suffix("").parts)
    if not parts or parts[0] != "src":
        raise ValueError(f"Expected file under src/, got: {relative_path}")

    module_parts = parts[1:]
    if not module_parts:
        raise ValueError(f"Could not resolve module for: {relative_path}")

    if module_parts[-1] == "__init__":
        module_parts = module_parts[:-1]
        if not module_parts:
            raise ValueError(f"Could not resolve package for: {relative_path}")
        module_name = ".".join(module_parts)
        package_name = module_name
    else:
        module_name = ".".join(module_parts)
        package_name = ".".join(module_parts[:-1])

    return ModuleContext(module_name=module_name, package_name=package_name)


def collect_imports(source: str, context: ModuleContext) -> list[ImportStatement]:
    """Parse Python source and return normalized import statements.

    Args:
        source: Python source code.
        context: Module metadata for the source file.

    Returns:
        Normalized import statements.
    """
    tree = ast.parse(source)
    imports: list[ImportStatement] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(_collect_absolute_imports(node))
        elif isinstance(node, ast.ImportFrom):
            imports.extend(_collect_from_imports(node, context))

    return imports


def matches_prefix(module_name: str, prefix: str) -> bool:
    """Return whether a module name matches a dotted prefix."""
    return module_name == prefix or module_name.startswith(f"{prefix}.")


def _collect_absolute_imports(node: ast.Import) -> list[ImportStatement]:
    return [
        ImportStatement(
            module=alias.name,
            line=node.lineno,
            category=classify_import(alias.name),
        )
        for alias in node.names
    ]


def _collect_from_imports(
    node: ast.ImportFrom,
    context: ModuleContext,
) -> list[ImportStatement]:
    base_module = resolve_import_from(
        package_name=context.package_name,
        module_name=node.module,
        level=node.level,
    )
    if not base_module:
        return []

    statements: list[ImportStatement] = []
    for alias in node.names:
        normalized_module = _normalize_from_import_alias(base_module, alias.name)
        statements.append(
            ImportStatement(
                module=normalized_module,
                line=node.lineno,
                category=classify_import(normalized_module),
            )
        )
    return statements


def _normalize_from_import_alias(base_module: str, alias_name: str) -> str:
    if alias_name == "*" or not alias_name.islower():
        return base_module
    return f"{base_module}.{alias_name}"


def resolve_import_from(
    package_name: str,
    module_name: str | None,
    level: int,
) -> str | None:
    """Resolve an ``ImportFrom`` node into a module reference."""
    if level == 0:
        return module_name

    package_parts = package_name.split(".") if package_name else []
    parent_index = len(package_parts) - (level - 1)
    if parent_index < 0:
        return None

    resolved_parts = package_parts[:parent_index]
    if module_name:
        resolved_parts.extend(module_name.split("."))

    if not resolved_parts:
        return None

    return ".".join(resolved_parts)


def classify_import(module_name: str) -> str:
    """Classify an import as stdlib, third-party, or local."""
    root_name = module_name.split(".", 1)[0]
    if root_name == "developer":
        return "local"
    if root_name in sys.stdlib_module_names:
        return "stdlib"
    return "third_party"
