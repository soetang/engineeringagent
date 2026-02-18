from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from engineeringagent.checks import emit_result_envelope
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.agents-backends-boundary"

_SRC_ROOT = Path("src/engineeringagent")
_AGENTS_ROOT = _SRC_ROOT / "agents"

_BACKENDS_IMPORT_PREFIX = "engineeringagent.agents.backends"
_RELATIVE_BACKENDS_IMPORT_PREFIX = "agents.backends"


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


def _format_violations(violations: list[_Violation]) -> list[str]:
    rendered: list[str] = []
    for violation in sorted(
        violations, key=lambda item: (str(item.path), item.lineno, item.message)
    ):
        rendered.append(f"{violation.path}:{violation.lineno}: {violation.message}")
    return rendered


def _normalize_import_from_module(node: ast.ImportFrom) -> str:
    module = node.module or ""
    if not module:
        return module

    if (
        getattr(node, "level", 0)
        and not module.startswith("engineeringagent.")
        and module.startswith(_RELATIVE_BACKENDS_IMPORT_PREFIX)
    ):
        return f"engineeringagent.{module}"

    return module


def _collect_violations(project_root: Path) -> list[str]:
    source_root = project_root / _SRC_ROOT
    if not source_root.exists():
        return [f"missing source package root: {_SRC_ROOT}"]

    violations: list[_Violation] = []

    for path in _iter_python_files(source_root):
        if _is_under(path, _AGENTS_ROOT):
            continue

        tree = _parse_module(path)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = _normalize_import_from_module(node)
                if module.startswith(_BACKENDS_IMPORT_PREFIX):
                    violations.append(
                        _Violation(
                            path=path.relative_to(project_root),
                            lineno=getattr(node, "lineno", 1),
                            message=(
                                f"imports backend package {module!r} outside agents boundary"
                            ),
                        )
                    )

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    if imported.startswith(_BACKENDS_IMPORT_PREFIX):
                        violations.append(
                            _Violation(
                                path=path.relative_to(project_root),
                                lineno=getattr(node, "lineno", 1),
                                message=(
                                    f"imports backend package {imported!r} outside agents boundary"
                                ),
                            )
                        )

    return _format_violations(violations)


def main() -> int:
    """Run the agent/backend import boundary fitness rule."""
    status = RuleStatus.PASS
    summary = "Agent/backend dependency boundary satisfied."
    violations: list[str] = []

    try:
        violations = _collect_violations(Path("."))
        status = RuleStatus.PASS if not violations else RuleStatus.FAIL
        if status == RuleStatus.FAIL:
            summary = f"Detected {len(violations)} backend boundary violation(s)."
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        status = RuleStatus.ERROR
        summary = f"Backend boundary scan failed: {exc}"

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
