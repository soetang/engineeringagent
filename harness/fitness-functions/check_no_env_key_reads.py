from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)
from engineeringagent.fitness.envelope import emit_result_envelope


RULE_ID = "architecture.no-env-key-reads"


def _iter_python_files(
    project_root: Path, *, scan_roots: tuple[str, ...]
) -> list[Path]:
    paths: list[Path] = []
    for root in scan_roots:
        root_path = project_root / root
        if not root_path.exists():
            continue
        paths.extend(root_path.rglob("*.py"))
    return sorted(paths, key=lambda path: path.relative_to(project_root).as_posix())


def _collect_import_aliases(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    os_module_names: set[str] = set()
    environ_names: set[str] = set()
    getenv_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    os_module_names.add(alias.asname or "os")
            continue

        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0:
            continue
        if node.module != "os":
            continue

        for alias in node.names:
            if alias.name == "environ":
                environ_names.add(alias.asname or "environ")
            elif alias.name == "getenv":
                getenv_names.add(alias.asname or "getenv")

    return os_module_names, environ_names, getenv_names


def _is_os_environ(expr: ast.AST, *, os_module_names: set[str]) -> bool:
    return (
        isinstance(expr, ast.Attribute)
        and expr.attr == "environ"
        and isinstance(expr.value, ast.Name)
        and expr.value.id in os_module_names
    )


def _collect_violations(project_root: Path) -> list[str]:
    violations: set[str] = set()
    scan_roots = ("src", "harness", "tests")

    for path in _iter_python_files(project_root, scan_roots=scan_roots):
        relpath = path.relative_to(project_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        try:
            tree = ast.parse(text, filename=relpath)
        except SyntaxError as exc:
            lineno = exc.lineno or 1
            violations.add(f"{relpath}:{lineno} failed to parse for env-key scan")
            continue

        os_module_names, environ_names, getenv_names = _collect_import_aliases(tree)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func

                if isinstance(func, ast.Name) and func.id in getenv_names:
                    lineno = getattr(node, "lineno", 1)
                    violations.add(
                        f"{relpath}:{lineno} forbidden env-key read via getenv(...)"
                    )
                    continue

                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.attr == "getenv" and func.value.id in os_module_names:
                        lineno = getattr(node, "lineno", 1)
                        violations.add(
                            f"{relpath}:{lineno} forbidden env-key read via os.getenv(...)"
                        )
                        continue

                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.value.id in environ_names:
                        if func.attr == "copy":
                            continue
                        if func.attr == "get":
                            lineno = getattr(node, "lineno", 1)
                            violations.add(
                                f"{relpath}:{lineno} forbidden env-key read via environ.get(...)"
                            )
                            continue

                if isinstance(func, ast.Attribute) and _is_os_environ(
                    func.value, os_module_names=os_module_names
                ):
                    if func.attr == "copy":
                        continue
                    if func.attr == "get":
                        lineno = getattr(node, "lineno", 1)
                        violations.add(
                            f"{relpath}:{lineno} forbidden env-key read via os.environ.get(...)"
                        )
                        continue
                    lineno = getattr(node, "lineno", 1)
                    violations.add(
                        f"{relpath}:{lineno} forbidden env-key read via os.environ.{func.attr}(...)"
                    )
                    continue

            if isinstance(node, ast.Subscript):
                value = node.value
                if _is_os_environ(value, os_module_names=os_module_names):
                    lineno = getattr(node, "lineno", 1)
                    violations.add(
                        f"{relpath}:{lineno} forbidden env-key read via os.environ[...]"
                    )
                    continue
                if isinstance(value, ast.Name) and value.id in environ_names:
                    lineno = getattr(node, "lineno", 1)
                    violations.add(
                        f"{relpath}:{lineno} forbidden env-key read via environ[...]"
                    )
                    continue

            if isinstance(node, ast.Compare):
                if not any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                    continue

                for comparator in node.comparators:
                    if _is_os_environ(comparator, os_module_names=os_module_names):
                        lineno = getattr(node, "lineno", 1)
                        violations.add(
                            f"{relpath}:{lineno} forbidden env-key read via 'X' in os.environ"
                        )
                        break
                    if (
                        isinstance(comparator, ast.Name)
                        and comparator.id in environ_names
                    ):
                        lineno = getattr(node, "lineno", 1)
                        violations.add(
                            f"{relpath}:{lineno} forbidden env-key read via 'X' in environ"
                        )
                        break

    return sorted(violations)


def main() -> int:
    violations = _collect_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "No environment-key reads detected."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} forbidden environment-key read(s)."
    )

    emit_result_envelope(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=RULE_ID,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
