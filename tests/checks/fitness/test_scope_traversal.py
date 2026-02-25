from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks.fitness.scope_traversal import (
    collect_symbol_call_locations,
    call_symbol,
    iter_function_defs,
    iter_nodes,
    iter_python_scope_files,
    parse_scope_modules,
    parse_scope_modules_or_fallback,
    tree_calls_any_symbol,
)


def test_iter_python_scope_files_collects_deterministic_scope(tmp_path: Path) -> None:
    package_dir = tmp_path / "src" / "engineeringagent" / "loop_runtime"
    package_dir.mkdir(parents=True)
    module_b = package_dir / "b_module.py"
    module_a = package_dir / "a_module.py"
    module_a.write_text("x = 1\n", encoding="utf-8")
    module_b.write_text("x = 2\n", encoding="utf-8")

    standalone = tmp_path / "src" / "engineeringagent" / "loop.py"
    standalone.parent.mkdir(parents=True, exist_ok=True)
    standalone.write_text("y = 3\n", encoding="utf-8")

    files = iter_python_scope_files(
        tmp_path,
        root_modules=(Path("src/engineeringagent/loop_runtime"), Path("missing")),
        standalone_modules=(
            Path("src/engineeringagent/loop.py"),
            Path("src/engineeringagent/not_a_file.py"),
        ),
    )

    assert files == [module_a, module_b, standalone]


def test_parse_scope_modules_returns_relative_paths_and_trees(tmp_path: Path) -> None:
    module_path = tmp_path / "src" / "engineeringagent" / "loop.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("def run() -> None:\n    return None\n", encoding="utf-8")

    parsed = parse_scope_modules(
        tmp_path,
        standalone_modules=(Path("src/engineeringagent/loop.py"),),
    )

    assert len(parsed) == 1
    relative_path, tree = parsed[0]
    assert relative_path == Path("src/engineeringagent/loop.py")
    assert isinstance(tree, ast.AST)


def test_parse_scope_modules_or_fallback_returns_fallback_when_scope_missing(
    tmp_path: Path,
) -> None:
    modules, violations = parse_scope_modules_or_fallback(
        tmp_path,
        root_modules=(Path("src/engineeringagent/loop_runtime"),),
        fallback_violation="scope missing",
    )

    assert modules == []
    assert violations == ["scope missing"]


def test_iter_nodes_and_call_symbol_cover_call_shapes() -> None:
    tree = ast.parse(
        "\n".join(
            [
                "fn()",
                "obj.method()",
                "(lambda f: f)(fn)",
            ]
        )
    )

    calls = list(iter_nodes(tree, ast.Call))
    assert [call_symbol(call) for call in calls] == ["fn", "method", None]


def test_iter_function_defs_yields_sync_and_async_functions() -> None:
    tree = ast.parse(
        "\n".join(
            [
                "def sync_fn():",
                "    return None",
                "",
                "async def async_fn():",
                "    return None",
            ]
        )
    )

    functions = list(iter_function_defs(tree))
    assert [function.name for function in functions] == ["sync_fn", "async_fn"]


def test_symbol_call_helpers_return_deterministic_matches() -> None:
    tree = ast.parse(
        "\n".join(
            [
                "run_checks()",
                "builder()",
                "other()",
                "obj.builder()",
            ]
        )
    )

    assert tree_calls_any_symbol(tree, {"run_checks"})
    assert not tree_calls_any_symbol(tree, {"missing"})
    assert collect_symbol_call_locations(tree, {"builder"}) == [
        (2, "builder"),
        (4, "builder"),
    ]
