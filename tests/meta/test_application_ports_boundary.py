from __future__ import annotations

import ast
from pathlib import Path


_APPLICATION_ROOT = Path("src/engineeringagent/application")


def _iter_application_modules() -> list[Path]:
    return sorted(path for path in _APPLICATION_ROOT.glob("*.py") if path.is_file())


def _inherits_protocol(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Protocol":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Protocol":
            return True
    return False


def test_application_infrastructure_protocols_live_in_ports() -> None:
    """Application modules must not declare infrastructure protocols."""

    violations: list[str] = []

    for path in _iter_application_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _inherits_protocol(node):
                violations.append(
                    f"{path}:{node.lineno}: move protocol {node.name} to engineeringagent.ports"
                )

    assert not violations, "\n".join(violations)


def test_ports_modules_do_not_import_application_modules() -> None:
    """Ports must not depend on application-layer modules."""

    ports_root = Path("src/engineeringagent/ports")
    violations: list[str] = []

    for path in sorted(ports_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "engineeringagent.application" or module.startswith(
                    "engineeringagent.application."
                ):
                    violations.append(
                        f"{path}:{node.lineno}: ports must not import application module {module}"
                    )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "engineeringagent.application" or alias.name.startswith(
                        "engineeringagent.application."
                    ):
                        violations.append(
                            f"{path}:{node.lineno}: ports must not import application module {alias.name}"
                        )

    assert not violations, "\n".join(violations)
