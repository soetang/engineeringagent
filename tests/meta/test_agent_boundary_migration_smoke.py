from __future__ import annotations

import ast
from pathlib import Path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _collect_typer_symbols(
    tree: ast.AST,
) -> tuple[set[str], set[str], set[str]]:
    typer_module_names: set[str] = set()
    typer_constructor_names: set[str] = set()
    typer_app_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "typer":
                    typer_module_names.add(alias.asname or "typer")
        if isinstance(node, ast.ImportFrom) and node.module == "typer":
            for alias in node.names:
                if alias.name == "Typer":
                    typer_constructor_names.add(alias.asname or "Typer")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if _is_typer_constructor_call(
            node.value,
            typer_module_names=typer_module_names,
            typer_constructor_names=typer_constructor_names,
        ):
            typer_app_names.add(target.id)

    return typer_module_names, typer_constructor_names, typer_app_names


def _is_typer_constructor_call(
    node: ast.AST,
    *,
    typer_module_names: set[str],
    typer_constructor_names: set[str],
) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return (
            func.attr == "Typer"
            and isinstance(func.value, ast.Name)
            and func.value.id in typer_module_names
        )
    return isinstance(func, ast.Name) and func.id in typer_constructor_names


def _module_uses_typer_registration(tree: ast.AST) -> bool:
    typer_module_names, typer_constructor_names, typer_app_names = (
        _collect_typer_symbols(tree)
    )
    if typer_app_names:
        return True

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_typer_constructor_call(
            node,
            typer_module_names=typer_module_names,
            typer_constructor_names=typer_constructor_names,
        ):
            return True
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"command", "callback"}
            and isinstance(func.value, ast.Name)
            and func.value.id in typer_app_names
        ):
            return True
    return False


def _module_imports_cli_bootstrap(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {
                    "engineeringagent.cli.app",
                    "engineeringagent.cli.typer",
                }:
                    return True
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in {
                "engineeringagent.cli.app",
                "engineeringagent.cli.typer",
            }:
                return True
    return False


def test_cli_package_no_longer_imports_opencode_start_agent() -> None:
    cli_root = Path("src/engineeringagent/cli")

    for path in _iter_python_files(cli_root):
        tree = ast.parse(_read_text(path), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            if not module.endswith("opencode.client"):
                continue
            assert all(alias.name != "start_agent" for alias in node.names), str(path)


def test_typer_bootstrap_registration_stays_inside_cli_package() -> None:
    src_root = Path("src/engineeringagent")
    cli_root = src_root / "cli"

    for path in _iter_python_files(src_root):
        if cli_root in path.parents:
            continue
        tree = ast.parse(_read_text(path), filename=str(path))
        assert not _module_uses_typer_registration(tree), str(path)
        assert not _module_imports_cli_bootstrap(tree), str(path)


def test_checks_api_no_longer_imports_opencode_start_agent() -> None:
    text = _read_text(Path("src/engineeringagent/checks/api.py"))
    assert "from engineeringagent.opencode.client import start_agent" not in text


def test_loop_no_longer_imports_opencode_start_agent() -> None:
    text = _read_text(Path("src/engineeringagent/loop.py"))
    assert "from .opencode.client import run_shell_command, start_agent" not in text
