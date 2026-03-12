from __future__ import annotations

import ast
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Iterator, TypeVar


_AstNodeT = TypeVar("_AstNodeT", bound=ast.AST)


LOOP_RUNTIME_ROOT = Path("src/engineeringagent/loop_runtime")
LOOP_ENTRY_MODULE = Path("src/engineeringagent/loop.py")
LOOP_PHASES_MODULE = Path("src/engineeringagent/adapters/runtime/iteration_phases.py")
PROMPT_RENDERER_MODULE = Path("src/engineeringagent/prompts/renderer.py")


def iter_python_scope_files(
    project_root: Path,
    *,
    root_modules: tuple[Path, ...] = (),
    standalone_modules: tuple[Path, ...] = (),
) -> list[Path]:
    """Return deterministic python file scope for boundary checks."""
    files: list[Path] = []
    for root_module in root_modules:
        root_path = project_root / root_module
        if not root_path.exists() or not root_path.is_dir():
            continue
        files.extend(sorted(root_path.rglob("*.py")))

    for module in standalone_modules:
        module_path = project_root / module
        if module_path.exists() and module_path.is_file():
            files.append(module_path)
    return files


def parse_scope_modules(
    project_root: Path,
    *,
    root_modules: tuple[Path, ...] = (),
    standalone_modules: tuple[Path, ...] = (),
) -> list[tuple[Path, ast.AST]]:
    """Return parsed trees keyed by project-relative path."""
    parsed: list[tuple[Path, ast.AST]] = []
    for file_path in iter_python_scope_files(
        project_root,
        root_modules=root_modules,
        standalone_modules=standalone_modules,
    ):
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        parsed.append((file_path.relative_to(project_root), tree))
    return parsed


def parse_scope_modules_or_fallback(
    project_root: Path,
    *,
    root_modules: tuple[Path, ...] = (),
    standalone_modules: tuple[Path, ...] = (),
    fallback_violation: str,
) -> tuple[list[tuple[Path, ast.AST]], list[str]]:
    """Parse scoped modules or return a deterministic missing-scope violation."""
    scope_modules = parse_scope_modules(
        project_root,
        root_modules=root_modules,
        standalone_modules=standalone_modules,
    )
    if scope_modules:
        return scope_modules, []
    return [], [fallback_violation]


def parse_loop_boundary_scope_or_fallback(
    project_root: Path,
    *,
    include_prompt_renderer: bool,
    fallback_violation: str,
) -> tuple[list[tuple[Path, ast.AST]], list[str]]:
    """Parse deterministic loop-boundary modules with shared scope paths."""
    standalone_modules: tuple[Path, ...] = (
        (LOOP_ENTRY_MODULE, LOOP_PHASES_MODULE, PROMPT_RENDERER_MODULE)
        if include_prompt_renderer
        else (LOOP_ENTRY_MODULE, LOOP_PHASES_MODULE)
    )
    return parse_scope_modules_or_fallback(
        project_root,
        root_modules=(LOOP_RUNTIME_ROOT,),
        standalone_modules=standalone_modules,
        fallback_violation=fallback_violation,
    )


def loop_scope_missing_violation(
    *,
    include_prompt_renderer: bool,
    remediation: str,
) -> str:
    """Build deterministic missing-scope violation text for loop boundary rules."""

    scope_label = (
        "loop runtime/prompt scope"
        if include_prompt_renderer
        else "loop runtime module scope"
    )
    return f"src/engineeringagent/loop_runtime:1 missing {scope_label}; {remediation}"


def collect_loop_boundary_violations(
    project_root: Path,
    *,
    include_prompt_renderer: bool,
    fallback_violation: str,
    module_violations: Callable[[Path, ast.AST], list[str]],
) -> list[str]:
    """Collect sorted loop-boundary violations via a shared traversal flow."""
    scope_modules, scope_violations = parse_loop_boundary_scope_or_fallback(
        project_root,
        include_prompt_renderer=include_prompt_renderer,
        fallback_violation=fallback_violation,
    )
    if scope_violations:
        return scope_violations

    violations: list[str] = []
    for relative, tree in scope_modules:
        violations.extend(module_violations(relative, tree))
    return sorted(violations)


def collect_loop_boundary_rule_violations(
    project_root: Path,
    *,
    include_prompt_renderer: bool,
    remediation: str,
    module_violations: Callable[[Path, ast.AST], list[str]],
) -> list[str]:
    """Collect loop-boundary violations using shared scope fallback wiring."""

    return collect_loop_boundary_violations(
        project_root,
        include_prompt_renderer=include_prompt_renderer,
        fallback_violation=loop_scope_missing_violation(
            include_prompt_renderer=include_prompt_renderer,
            remediation=remediation,
        ),
        module_violations=module_violations,
    )


def iter_nodes(tree: ast.AST, node_type: type[_AstNodeT]) -> Iterator[_AstNodeT]:
    """Yield nodes of a specific type in deterministic walk order."""
    for node in ast.walk(tree):
        if isinstance(node, node_type):
            yield node


def sorted_violation_messages(violations: list[tuple[int, str]]) -> list[str]:
    """Return sorted violation messages from ``(line, message)`` tuples."""
    return [message for _, message in sorted(violations)]


def collect_node_violations(
    tree: ast.AST,
    *,
    node_type: type[_AstNodeT],
    violation_for_node: Callable[[_AstNodeT], str | Collection[str] | None],
) -> list[tuple[int, str]]:
    """Collect unsorted ``(line, message)`` violations for one AST node type."""

    violations: list[tuple[int, str]] = []
    for node in iter_nodes(tree, node_type):
        raw_message = violation_for_node(node)
        if raw_message is None:
            continue
        messages = (
            [raw_message]
            if isinstance(raw_message, str)
            else [message for message in raw_message if message]
        )
        if not messages:
            continue
        lineno = int(getattr(node, "lineno", 0))
        for message in messages:
            violations.append((lineno, message))
    return violations


def iter_function_defs(
    tree: ast.AST,
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield function nodes in deterministic walk order."""
    for node in iter_nodes(tree, ast.AST):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def call_symbol(call: ast.Call) -> str | None:
    """Resolve a call symbol from Name/Attribute call sites."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def iter_calls_with_symbols(
    tree: ast.AST,
    symbols: Collection[str],
) -> Iterator[tuple[ast.Call, str]]:
    """Yield calls whose resolved symbols are in ``symbols``."""
    for node in iter_nodes(tree, ast.Call):
        symbol = call_symbol(node)
        if symbol is None or symbol not in symbols:
            continue
        yield node, symbol


def collect_symbol_call_locations(
    tree: ast.AST,
    symbols: Collection[str],
) -> list[tuple[int, str]]:
    """Collect deterministic ``(lineno, symbol)`` call matches for ``symbols``."""

    return sorted(
        (node.lineno, symbol) for node, symbol in iter_calls_with_symbols(tree, symbols)
    )


def collect_import_from_symbol_violations(
    tree: ast.AST,
    *,
    forbidden_symbols: Collection[str],
    message_builder: Callable[[int, str], str],
) -> list[str]:
    """Collect sorted import-from violations for forbidden imported symbols."""

    violations = collect_node_violations(
        tree,
        node_type=ast.ImportFrom,
        violation_for_node=lambda node: [
            message_builder(int(getattr(node, "lineno", 0)), alias.name)
            for alias in node.names
            if alias.name in forbidden_symbols
        ],
    )
    return sorted_violation_messages(violations)


def collect_call_symbol_violations(
    tree: ast.AST,
    *,
    forbidden_symbols: Collection[str],
    message_builder: Callable[[int, str], str],
) -> list[str]:
    """Collect sorted call-site violations for forbidden symbols."""

    violations = collect_node_violations(
        tree,
        node_type=ast.Call,
        violation_for_node=lambda node: (
            message_builder(int(getattr(node, "lineno", 0)), symbol)
            if (symbol := call_symbol(node)) is not None and symbol in forbidden_symbols
            else None
        ),
    )
    return sorted_violation_messages(violations)


def tree_calls_any_symbol(
    tree: ast.AST,
    symbols: Collection[str],
) -> bool:
    """Return whether ``tree`` contains at least one call to ``symbols``."""

    return any(iter_calls_with_symbols(tree, symbols))


def collect_function_symbol_call_violations(
    tree: ast.AST,
    *,
    trigger_symbols: Collection[str],
    forbidden_symbols: Collection[str],
    message_builder: Callable[[int, str], str],
) -> list[str]:
    """Collect sorted function-scope symbol-call violations.

    A function is inspected when it calls at least one symbol in
    ``trigger_symbols``. Any call to ``forbidden_symbols`` inside that function
    emits a violation message using ``message_builder``.
    """

    violations: list[tuple[int, str]] = []
    for node in iter_function_defs(tree):
        if not tree_calls_any_symbol(node, trigger_symbols):
            continue
        for lineno, symbol in collect_symbol_call_locations(node, forbidden_symbols):
            violations.append((lineno, message_builder(lineno, symbol)))
    return sorted_violation_messages(violations)
