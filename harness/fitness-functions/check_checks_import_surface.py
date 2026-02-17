from __future__ import annotations

import ast
from pathlib import Path

import engineeringagent.checks as checks
from engineeringagent.checks import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
    emit_result_envelope,
)


RULE_ID = "architecture.checks-import-surface"

_EXCLUDED_PACKAGES = {
    "checks",
    "fitness",
    "retry_feedback",
}


def _iter_python_files(project_root: Path) -> list[Path]:
    src_root = project_root / "src" / "engineeringagent"
    if not src_root.exists():
        return []
    paths: list[Path] = []
    for path in src_root.rglob("*.py"):
        if not path.is_file():
            continue

        rel = path.relative_to(src_root)
        if rel.parts[0] in _EXCLUDED_PACKAGES:
            continue
        if rel.parts[0] == "__pycache__":
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: path.relative_to(project_root).as_posix())


def _module_name_for_path(project_root: Path, path: Path) -> str | None:
    try:
        rel = path.relative_to(project_root / "src")
    except ValueError:
        return None
    if rel.suffix != ".py":
        return None
    parts = list(rel.with_suffix("").parts)
    if not parts:
        return None
    return ".".join(parts)


def _resolve_import_from_base(module_name: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    module_parts = module_name.split(".")
    if node.level > len(module_parts):
        return None

    base_parts = module_parts[: -node.level]
    if node.module:
        base_parts.extend(node.module.split("."))
    if not base_parts:
        return None
    return ".".join(base_parts)


def _collect_violations(project_root: Path) -> list[str]:
    allowed_names = set(getattr(checks, "__all__", ()))
    violations: set[str] = set()

    for path in _iter_python_files(project_root):
        relpath = path.relative_to(project_root).as_posix()
        module_name = _module_name_for_path(project_root, path)
        if module_name is None:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        try:
            tree = ast.parse(text, filename=relpath)
        except SyntaxError as exc:
            lineno = exc.lineno or 1
            violations.add(f"{relpath}:{lineno} failed to parse for checks import scan")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name == "engineeringagent.checks":
                        continue
                    if name.startswith("engineeringagent.checks."):
                        violations.add(
                            f"{relpath}:{node.lineno} imports checks submodule {name}"
                        )
                continue

            if not isinstance(node, ast.ImportFrom):
                continue

            base = _resolve_import_from_base(module_name, node)
            if base is None:
                continue

            if base == "engineeringagent.checks":
                for alias in node.names:
                    if alias.name == "*":
                        violations.add(
                            f"{relpath}:{node.lineno} star-import from engineeringagent.checks is not allowed"
                        )
                        continue
                    if alias.name not in allowed_names:
                        violations.add(
                            f"{relpath}:{node.lineno} imports disallowed name {alias.name} from engineeringagent.checks"
                        )
                continue

            if base.startswith("engineeringagent.checks."):
                violations.add(
                    f"{relpath}:{node.lineno} imports checks submodule {base}"
                )
                continue

    if violations:
        violations.add(
            "remediation: replace engineeringagent.checks.<submodule> imports with `from engineeringagent.checks import <allowed_name>`"
        )
    return sorted(violations)


def main() -> int:
    violations = _collect_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Production modules only import from the supported engineeringagent.checks surface."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} unsupported checks import(s)."
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
