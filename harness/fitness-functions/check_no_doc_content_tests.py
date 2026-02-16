from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.fitness.envelope import emit_result_envelope


RULE_ID = "architecture.no-doc-content-tests"


def _extract_repo_root_relpath(expr: ast.AST, *, repo_root_name: str) -> str | None:
    """Extract relpath from expressions like: repo_root / "docs" / "x.md"."""

    segments: list[str] = []
    cursor: ast.AST = expr
    while isinstance(cursor, ast.BinOp) and isinstance(cursor.op, ast.Div):
        right = cursor.right
        if not (isinstance(right, ast.Constant) and isinstance(right.value, str)):
            return None
        segments.insert(0, right.value)
        cursor = cursor.left

    if not (isinstance(cursor, ast.Name) and cursor.id == repo_root_name):
        return None

    normalized = "/".join(part.strip("/") for part in segments if part)
    return normalized or None


def _is_banned_doc_target(relpath: str) -> bool:
    if relpath == "README.md":
        return True
    if relpath.startswith("docs/") and relpath.endswith(".md"):
        return True
    return False


def _is_allowed_doc_target(relpath: str) -> bool:
    # Functional exceptions.
    if relpath.startswith("harness/reviewers/prompts/") and relpath.endswith(".md"):
        return True

    # Generated artifact sync is allowed.
    if relpath == "docs/fitness-functions/rules.md":
        return True

    return False


def _iter_python_test_files(project_root: Path) -> list[Path]:
    tests_root = project_root / "tests"
    if not tests_root.exists():
        return []
    return sorted(tests_root.rglob("*.py"))


def _scan_function_body(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    file_rel: Path,
    violations: list[str],
    repo_root_name: str,
) -> None:
    relpaths_by_name: dict[str, str] = {}

    def _note_call(lineno: int, relpath: str) -> None:
        if not _is_banned_doc_target(relpath):
            return
        if _is_allowed_doc_target(relpath):
            return
        violations.append(
            f"{file_rel}:{lineno} tests must not assert wording in repo docs; "
            f"remove read/word assertions for {relpath}"
        )

    def _scan_expr(expr: ast.AST) -> None:
        for child in ast.walk(expr):
            if not isinstance(child, ast.Call):
                continue

            # _read_repo_text(repo_root, "docs/...md") helper.
            if isinstance(child.func, ast.Name) and child.func.id == "_read_repo_text":
                if len(child.args) >= 2:
                    root_arg = child.args[0]
                    path_arg = child.args[1]
                    if (
                        isinstance(root_arg, ast.Name)
                        and root_arg.id == repo_root_name
                        and isinstance(path_arg, ast.Constant)
                        and isinstance(path_arg.value, str)
                    ):
                        _note_call(getattr(child, "lineno", 1), path_arg.value)
                continue

            # Path.read_text(...)
            if not (
                isinstance(child.func, ast.Attribute) and child.func.attr == "read_text"
            ):
                continue

            receiver = child.func.value
            relpath = _extract_repo_root_relpath(
                receiver, repo_root_name=repo_root_name
            )
            if relpath is None and isinstance(receiver, ast.Name):
                relpath = relpaths_by_name.get(receiver.id)
            if relpath is None:
                continue

            _note_call(getattr(child, "lineno", 1), relpath)

    def _scan_statement(statement: ast.stmt) -> None:
        if isinstance(statement, ast.Assign):
            if len(statement.targets) == 1 and isinstance(
                statement.targets[0], ast.Name
            ):
                relpath = _extract_repo_root_relpath(
                    statement.value,
                    repo_root_name=repo_root_name,
                )
                if relpath is not None:
                    relpaths_by_name[statement.targets[0].id] = relpath
            _scan_expr(statement.value)
            return

        if isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            if statement.value is not None:
                relpath = _extract_repo_root_relpath(
                    statement.value,
                    repo_root_name=repo_root_name,
                )
                if relpath is not None:
                    relpaths_by_name[statement.target.id] = relpath
                _scan_expr(statement.value)
            return

        if isinstance(statement, ast.Expr):
            _scan_expr(statement.value)
            return

        if isinstance(statement, ast.Return) and statement.value is not None:
            _scan_expr(statement.value)
            return

        if isinstance(statement, ast.If):
            _scan_expr(statement.test)
            for child in statement.body:
                _scan_statement(child)
            for child in statement.orelse:
                _scan_statement(child)
            return

        # Best-effort: scan any expressions inside other statements.
        for child in ast.walk(statement):
            if isinstance(child, ast.expr):
                _scan_expr(child)

    for statement in node.body:
        _scan_statement(statement)


def _doc_content_test_violations(project_root: Path) -> list[str]:
    violations: list[str] = []
    for path in _iter_python_test_files(project_root):
        file_rel = path.relative_to(project_root)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            lineno = exc.lineno or 1
            violations.append(
                f"{file_rel}:{lineno} failed to parse for doc-content guard"
            )
            continue

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _scan_function_body(
                    node,
                    file_rel=file_rel,
                    violations=violations,
                    repo_root_name="repo_root",
                )

    return sorted(set(violations))


def main() -> int:
    violations = _doc_content_test_violations(Path("."))
    status = "pass" if not violations else "fail"
    summary = (
        "No brittle doc-content tests detected."
        if status == "pass"
        else f"Detected {len(violations)} doc-content test(s)."
    )

    emit_result_envelope(
        rule_id=RULE_ID,
        status=status,
        severity="error",
        summary=summary,
        violations=violations,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
