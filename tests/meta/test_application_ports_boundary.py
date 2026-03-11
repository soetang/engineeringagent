from __future__ import annotations

import ast
from pathlib import Path


_APPLICATION_ROOT = Path("src/engineeringagent/application")
_ALLOWED_PROTOCOL_MODULES = {
    _APPLICATION_ROOT / "prompt_builder.py",
}


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
    violations: list[str] = []

    for path in _iter_application_modules():
        if path in _ALLOWED_PROTOCOL_MODULES:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _inherits_protocol(node):
                violations.append(
                    f"{path}:{node.lineno}: move protocol {node.name} to engineeringagent.ports"
                )

    assert not violations, "\n".join(violations)
