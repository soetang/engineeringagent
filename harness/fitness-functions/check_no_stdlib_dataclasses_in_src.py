from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.fitness.envelope import emit_result_envelope


RULE_ID = "architecture.no-stdlib-dataclasses-in-src"
SCOPED_ROOT = Path("src/engineeringagent")


def _violation(path: Path, node: ast.AST, detail: str) -> str:
    line = getattr(node, "lineno", 1)
    column = getattr(node, "col_offset", 0) + 1
    return (
        f"{path.as_posix()}:{line}:{column} {detail}; "
        "use pydantic.BaseModel for production models."
    )


def _decorator_is_dataclass(
    decorator: ast.expr,
    *,
    dataclass_symbol_names: set[str],
    dataclasses_module_aliases: set[str],
) -> bool:
    if isinstance(decorator, ast.Name):
        return decorator.id in dataclass_symbol_names
    if isinstance(decorator, ast.Attribute) and isinstance(decorator.value, ast.Name):
        return (
            decorator.attr == "dataclass"
            and decorator.value.id in dataclasses_module_aliases
        )
    if isinstance(decorator, ast.Call):
        return _decorator_is_dataclass(
            decorator.func,
            dataclass_symbol_names=dataclass_symbol_names,
            dataclasses_module_aliases=dataclasses_module_aliases,
        )
    return False


def _scan_file(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path.as_posix())

    violations: list[str] = []
    dataclasses_module_aliases: set[str] = set()
    dataclass_symbol_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "dataclasses":
                    name = alias.asname or alias.name
                    dataclasses_module_aliases.add(name)
                    violations.append(
                        _violation(path, node, "stdlib dataclasses import is forbidden")
                    )
        elif isinstance(node, ast.ImportFrom) and node.module == "dataclasses":
            for alias in node.names:
                if alias.name == "dataclass":
                    dataclass_symbol_names.add(alias.asname or alias.name)
            violations.append(
                _violation(path, node, "stdlib dataclasses import is forbidden")
            )

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.FunctionDef)):
            for decorator in node.decorator_list:
                if _decorator_is_dataclass(
                    decorator,
                    dataclass_symbol_names=dataclass_symbol_names,
                    dataclasses_module_aliases=dataclasses_module_aliases,
                ):
                    violations.append(
                        _violation(
                            path, decorator, "stdlib dataclass decorator is forbidden"
                        )
                    )
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in dataclasses_module_aliases:
                violations.append(
                    _violation(path, node, "dataclasses namespace usage is forbidden")
                )

    return sorted(set(violations))


def main() -> int:
    files = sorted(SCOPED_ROOT.rglob("*.py"))

    violations: list[str] = []
    for file_path in files:
        violations.extend(_scan_file(file_path))

    status = "pass" if not violations else "fail"
    summary = (
        "No stdlib dataclasses usage detected in src/engineeringagent."
        if status == "pass"
        else (
            "Detected stdlib dataclasses usage in src/engineeringagent. "
            "Migrate models to pydantic.BaseModel."
        )
    )

    emit_result_envelope(
        rule_id=RULE_ID,
        status=status,
        severity="error",
        summary=summary,
        violations=sorted(set(violations)),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
