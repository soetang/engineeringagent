from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


_SRC_ROOT = Path("src/engineeringagent")


@dataclass(frozen=True)
class _Violation:
    path: Path
    lineno: int
    message: str


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _is_under(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _parse_module(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _format_violations(violations: list[_Violation]) -> str:
    lines: list[str] = []
    for violation in sorted(
        violations, key=lambda item: (str(item.path), item.lineno, item.message)
    ):
        lines.append(f"{violation.path}:{violation.lineno}: {violation.message}")
    return "\n".join(lines)


def test_no_start_agent_imports_or_refs_outside_boundary() -> None:
    allowed_dirs = (_SRC_ROOT / "agents" / "backends" / "opencode",)
    violations: list[_Violation] = []

    for path in _iter_python_files(_SRC_ROOT):
        if any(_is_under(path, allowed) for allowed in allowed_dirs):
            continue

        tree = _parse_module(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if (
                    module.endswith("opencode.client")
                    or module.endswith("opencode.backend")
                    or module.endswith("opencode")
                ):
                    for alias in node.names:
                        if alias.name == "start_agent":
                            violations.append(
                                _Violation(
                                    path=path,
                                    lineno=getattr(node, "lineno", 1),
                                    message=f"imports start_agent from {module!r}",
                                )
                            )

            if isinstance(node, ast.Attribute) and node.attr == "start_agent":
                violations.append(
                    _Violation(
                        path=path,
                        lineno=getattr(node, "lineno", 1),
                        message="references attribute start_agent",
                    )
                )

            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "start_agent":
                    violations.append(
                        _Violation(
                            path=path,
                            lineno=getattr(node, "lineno", 1),
                            message="calls start_agent",
                        )
                    )

    assert not violations, "start_agent bypasses boundary:\n" + _format_violations(
        violations
    )


def test_no_format_json_keyword_argument_outside_agents() -> None:
    allowed_dir = _SRC_ROOT / "agents"
    violations: list[_Violation] = []

    for path in _iter_python_files(_SRC_ROOT):
        if _is_under(path, allowed_dir):
            continue

        tree = _parse_module(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            for keyword in node.keywords:
                if keyword.arg != "format":
                    continue
                value = keyword.value
                if isinstance(value, ast.Constant) and value.value == "json":
                    violations.append(
                        _Violation(
                            path=path,
                            lineno=getattr(node, "lineno", 1),
                            message='passes format="json" outside agents boundary',
                        )
                    )

    assert not violations, 'format="json" bypasses boundary:\n' + _format_violations(
        violations
    )


def test_no_configured_agent_runner_imports_outside_bootstrap_or_adapters() -> None:
    allowed_dirs = (
        _SRC_ROOT / "bootstrap",
        _SRC_ROOT / "adapters" / "agents",
    )
    violations: list[_Violation] = []

    for path in _iter_python_files(_SRC_ROOT):
        if any(_is_under(path, allowed) for allowed in allowed_dirs):
            continue

        tree = _parse_module(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue

            module = node.module or ""
            if module != "engineeringagent.adapters.agents":
                continue

            for alias in node.names:
                if alias.name != "ConfiguredAgentRunner":
                    continue
                violations.append(
                    _Violation(
                        path=path,
                        lineno=getattr(node, "lineno", 1),
                        message="imports ConfiguredAgentRunner outside bootstrap/adapters",
                    )
                )

    assert not violations, (
        "ConfiguredAgentRunner bypasses bootstrap-owned wiring:\n"
        + _format_violations(violations)
    )
