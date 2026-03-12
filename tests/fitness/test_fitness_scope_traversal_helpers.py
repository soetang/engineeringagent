from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.adapters.quality.fitness.boundary_reporting import (
    build_boundary_rule_result,
)
from engineeringagent.adapters.quality.fitness.scope_traversal import (
    LOOP_ENTRY_MODULE,
    LOOP_RUNTIME_ROOT,
    PROMPT_RENDERER_MODULE,
    call_symbol,
    collect_function_symbol_call_violations,
    collect_loop_boundary_rule_violations,
    collect_loop_boundary_violations,
    collect_node_violations,
    collect_symbol_call_locations,
    iter_calls_with_symbols,
    iter_function_defs,
    iter_nodes,
    iter_python_scope_files,
    loop_scope_missing_violation,
    parse_loop_boundary_scope_or_fallback,
    parse_scope_modules,
    parse_scope_modules_or_fallback,
    sorted_violation_messages,
    tree_calls_any_symbol,
)


def test_build_boundary_rule_result_pass_and_fail_contract() -> None:
    passed = build_boundary_rule_result(
        rule_id="architecture.example",
        violations=[],
        pass_summary="Boundary satisfied.",
        fail_summary_label="example",
    )
    assert passed.status == "pass"
    assert passed.summary == "Boundary satisfied."
    assert passed.violations == []

    failed = build_boundary_rule_result(
        rule_id="architecture.example",
        violations=["a", "b"],
        pass_summary="Boundary satisfied.",
        fail_summary_label="example",
    )
    assert failed.status == "fail"
    assert failed.summary == "Detected 2 example violation(s)."
    assert failed.violations == ["a", "b"]


def test_scope_parsing_helpers_cover_loop_scope_and_fallbacks(tmp_path: Path) -> None:
    runtime_dir = tmp_path / LOOP_RUNTIME_ROOT
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "a.py").write_text("x = 1\n", encoding="utf-8")
    (runtime_dir / "z.py").write_text("y = 2\n", encoding="utf-8")

    loop_path = tmp_path / LOOP_ENTRY_MODULE
    loop_path.parent.mkdir(parents=True, exist_ok=True)
    loop_path.write_text("def run():\n    return True\n", encoding="utf-8")

    renderer_path = tmp_path / PROMPT_RENDERER_MODULE
    renderer_path.parent.mkdir(parents=True, exist_ok=True)
    renderer_path.write_text("def render():\n    return ''\n", encoding="utf-8")

    files = iter_python_scope_files(
        tmp_path,
        root_modules=(LOOP_RUNTIME_ROOT,),
        standalone_modules=(LOOP_ENTRY_MODULE,),
    )
    assert files == [runtime_dir / "a.py", runtime_dir / "z.py", loop_path]

    parsed = parse_scope_modules(
        tmp_path,
        root_modules=(LOOP_RUNTIME_ROOT,),
        standalone_modules=(LOOP_ENTRY_MODULE,),
    )
    assert [relative for relative, _ in parsed] == [
        Path("src/engineeringagent/loop_runtime/a.py"),
        Path("src/engineeringagent/loop_runtime/z.py"),
        Path("src/engineeringagent/loop.py"),
    ]

    with_prompt, violations = parse_loop_boundary_scope_or_fallback(
        tmp_path,
        include_prompt_renderer=True,
        fallback_violation="missing",
    )
    assert not violations
    assert Path("src/engineeringagent/prompts/renderer.py") in {
        relative for relative, _ in with_prompt
    }

    without_prompt, violations = parse_loop_boundary_scope_or_fallback(
        tmp_path,
        include_prompt_renderer=False,
        fallback_violation="missing",
    )
    assert not violations
    assert Path("src/engineeringagent/prompts/renderer.py") not in {
        relative for relative, _ in without_prompt
    }

    empty_scope, fallback = parse_scope_modules_or_fallback(
        tmp_path,
        root_modules=(Path("does/not/exist"),),
        fallback_violation="scope-missing",
    )
    assert empty_scope == []
    assert fallback == ["scope-missing"]

    assert "loop runtime/prompt scope" in loop_scope_missing_violation(
        include_prompt_renderer=True,
        remediation="fix",
    )
    assert "loop runtime module scope" in loop_scope_missing_violation(
        include_prompt_renderer=False,
        remediation="fix",
    )


def test_collect_loop_boundary_violations_fallback_and_sorting(tmp_path: Path) -> None:
    fallback = collect_loop_boundary_violations(
        tmp_path,
        include_prompt_renderer=False,
        fallback_violation="scope missing",
        module_violations=lambda _relative, _tree: ["never"],
    )
    assert fallback == ["scope missing"]

    runtime_dir = tmp_path / LOOP_RUNTIME_ROOT
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "mod.py").write_text("x = 1\n", encoding="utf-8")
    loop_path = tmp_path / LOOP_ENTRY_MODULE
    loop_path.parent.mkdir(parents=True, exist_ok=True)
    loop_path.write_text("x = 2\n", encoding="utf-8")

    violations = collect_loop_boundary_rule_violations(
        tmp_path,
        include_prompt_renderer=False,
        remediation="clean up",
        module_violations=lambda relative, _tree: [
            f"{relative}:10 z",
            f"{relative}:1 a",
        ],
    )
    assert violations == sorted(violations)


def test_ast_symbol_and_node_helpers_collect_deterministic_violations() -> None:
    tree = ast.parse(
        "\n".join(
            [
                "from x import y",
                "",
                "def a():",
                "    run_checks()",
                "    build_fitness_failure_feedback()",
                "",
                "async def b():",
                "    helper()",
            ]
        )
    )

    function_names = [node.name for node in iter_function_defs(tree)]
    assert function_names == ["a", "b"]

    import_nodes = list(iter_nodes(tree, ast.ImportFrom))
    assert len(import_nodes) == 1

    attr_stmt = ast.parse("obj.fn()\n").body[0]
    assert isinstance(attr_stmt, ast.Expr)
    attr_call = attr_stmt.value
    assert isinstance(attr_call, ast.Call)
    assert call_symbol(attr_call) == "fn"

    lambda_stmt = ast.parse("(lambda: 1)()\n").body[0]
    assert isinstance(lambda_stmt, ast.Expr)
    lambda_call = lambda_stmt.value
    assert isinstance(lambda_call, ast.Call)
    assert call_symbol(lambda_call) is None

    calls = list(iter_calls_with_symbols(tree, {"run_checks", "helper"}))
    assert [symbol for _, symbol in calls] == ["run_checks", "helper"]

    locations = collect_symbol_call_locations(
        tree,
        {"run_checks", "build_fitness_failure_feedback"},
    )
    assert locations == [
        (4, "run_checks"),
        (5, "build_fitness_failure_feedback"),
    ]
    assert tree_calls_any_symbol(tree, {"run_checks"})
    assert not tree_calls_any_symbol(tree, {"missing"})

    node_violations = collect_node_violations(
        tree,
        node_type=ast.ImportFrom,
        violation_for_node=lambda _node: ["b", "", "a"],
    )
    assert sorted_violation_messages(node_violations) == ["a", "b"]

    function_violations = collect_function_symbol_call_violations(
        tree,
        trigger_symbols={"run_checks"},
        forbidden_symbols={"build_fitness_failure_feedback", "helper"},
        message_builder=lambda lineno, symbol: f"{lineno}:{symbol}",
    )
    assert function_violations == ["5:build_fitness_failure_feedback"]
