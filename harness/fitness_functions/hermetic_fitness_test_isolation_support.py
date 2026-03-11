from __future__ import annotations

import ast
from collections.abc import Callable


class TaintState:
    """Tracks tainted names and mapping keys while scanning a function body."""

    def __init__(self) -> None:
        """Initialize empty taint-tracking collections."""
        self.tainted_names: set[str] = set()
        self.tainted_mapping_keys: dict[str, set[str]] = {}

    def is_tainted(self, expr: ast.AST) -> bool:
        """Return whether the expression flows from a tainted source."""
        return is_tainted(expr, tainted_names=self.tainted_names)

    def mapping_keys(self, expr: ast.AST) -> set[str]:
        """Return mapping keys whose values flow from tainted sources."""
        return mapping_taint_keys(
            expr,
            tainted_names=self.tainted_names,
            tainted_mapping_keys=self.tainted_mapping_keys,
        )

    def update_assignment(self, name: str, value: ast.AST) -> None:
        """Refresh taint state after assigning a new value to a name."""
        if self.is_tainted(value):
            self.tainted_names.add(name)
        else:
            self.tainted_names.discard(name)

        tainted_keys = self.mapping_keys(value)
        if tainted_keys:
            self.tainted_mapping_keys[name] = tainted_keys
            return
        self.tainted_mapping_keys.pop(name, None)


def is_tainted(expr: ast.AST, *, tainted_names: set[str]) -> bool:
    """Return whether an expression resolves from repo-root-derived data."""
    if isinstance(expr, ast.Name):
        return expr.id == "repo_root" or expr.id in tainted_names
    if isinstance(expr, ast.Attribute):
        return is_tainted(expr.value, tainted_names=tainted_names)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
        return is_tainted(expr.left, tainted_names=tainted_names)
    if isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Name) and expr.func.id == "Path":
            return any(is_tainted(arg, tainted_names=tainted_names) for arg in expr.args)
        if isinstance(expr.func, ast.Attribute):
            return is_tainted(expr.func.value, tainted_names=tainted_names)
    return False


def tainted_source_names(
    expr: ast.AST,
    *,
    tainted_sources: dict[str, set[str]],
) -> set[str]:
    """Return originating tainted parameter names for an expression."""
    if isinstance(expr, ast.Name):
        if expr.id == "repo_root":
            return {"repo_root"}
        return set(tainted_sources.get(expr.id, set()))
    if isinstance(expr, ast.Attribute):
        return tainted_source_names(expr.value, tainted_sources=tainted_sources)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
        return tainted_source_names(expr.left, tainted_sources=tainted_sources)
    if isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Name) and expr.func.id == "Path":
            tainted_sources_found: set[str] = set()
            for arg in expr.args:
                tainted_sources_found.update(
                    tainted_source_names(arg, tainted_sources=tainted_sources)
                )
            return tainted_sources_found
        if isinstance(expr.func, ast.Attribute):
            return tainted_source_names(expr.func.value, tainted_sources=tainted_sources)
    return set()


def mapping_taint_keys(
    expr: ast.AST,
    *,
    tainted_names: set[str],
    tainted_mapping_keys: dict[str, set[str]],
) -> set[str]:
    """Return dict keys whose values are tainted within the expression."""
    if isinstance(expr, ast.Name):
        return set(tainted_mapping_keys.get(expr.id, set()))
    if not isinstance(expr, ast.Dict):
        return set()

    tainted_keys: set[str] = set()
    for key, value in zip(expr.keys, expr.values, strict=False):
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            continue
        if is_tainted(value, tainted_names=tainted_names):
            tainted_keys.add(key.value)
    return tainted_keys


def scan_statement(
    statement: ast.stmt,
    *,
    scan_expression: Callable[[ast.AST], None],
    scan_statement_recursively: Callable[[ast.stmt], None],
    handle_name_assignment: Callable[[str, ast.AST], None],
    skip_classdefs: bool,
) -> None:
    """Scan a statement while delegating recursion and assignment handling."""
    if isinstance(statement, ast.ClassDef) and skip_classdefs:
        return

    if isinstance(statement, ast.Assign):
        if len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            handle_name_assignment(statement.targets[0].id, statement.value)
        scan_expression(statement.value)
        return

    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        if statement.value is not None:
            handle_name_assignment(statement.target.id, statement.value)
            scan_expression(statement.value)
        return

    if isinstance(statement, ast.Expr):
        scan_expression(statement.value)
        return

    if isinstance(statement, ast.Return) and statement.value is not None:
        scan_expression(statement.value)
        return

    if isinstance(statement, ast.If):
        scan_expression(statement.test)
        for child in statement.body:
            scan_statement_recursively(child)
        for child in statement.orelse:
            scan_statement_recursively(child)
        return

    if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While)):
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.expr):
                scan_expression(child)
        for child in getattr(statement, "body", []):
            scan_statement_recursively(child)
        for child in getattr(statement, "orelse", []):
            scan_statement_recursively(child)
        return

    for child in ast.walk(statement):
        if isinstance(child, ast.expr):
            scan_expression(child)
