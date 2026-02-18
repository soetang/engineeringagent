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


RULE_ID = "architecture.agents-opencode-boundary"

_SRC_ROOT = Path("src/engineeringagent")
_AGENTS_ROOT = _SRC_ROOT / "agents"
_OPENCODE_BACKEND_ROOT = _AGENTS_ROOT / "backends" / "opencode"

_OPENCODE_BACKEND_IMPORT_PREFIX = "engineeringagent.agents.backends.opencode"
_LEGACY_OPENCODE_IMPORT_PREFIX = "engineeringagent.opencode"

_RELATIVE_OPENCODE_BACKEND_IMPORT_PREFIX = "agents.backends.opencode"
_RELATIVE_LEGACY_OPENCODE_IMPORT_PREFIX = "opencode"


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


def _collect_violations(project_root: Path) -> list[str]:
    source_root = project_root / _SRC_ROOT
    if not source_root.exists():
        return [f"missing source package root: {_SRC_ROOT}"]

    violations: list[_Violation] = []

    for path in _iter_python_files(source_root):
        tree = _parse_module(path)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                resolved_module = module
                if (
                    getattr(node, "level", 0)
                    and module
                    and not module.startswith("engineeringagent.")
                    and (
                        module.startswith(_RELATIVE_OPENCODE_BACKEND_IMPORT_PREFIX)
                        or module.startswith(_RELATIVE_LEGACY_OPENCODE_IMPORT_PREFIX)
                    )
                ):
                    resolved_module = f"engineeringagent.{module}"

                if resolved_module.startswith(_LEGACY_OPENCODE_IMPORT_PREFIX):
                    violations.append(
                        _Violation(
                            path=path.relative_to(project_root),
                            lineno=getattr(node, "lineno", 1),
                            message=(
                                f"imports legacy opencode package {resolved_module!r} (expected {_OPENCODE_BACKEND_IMPORT_PREFIX!r})"
                            ),
                        )
                    )

                if resolved_module.startswith(
                    _OPENCODE_BACKEND_IMPORT_PREFIX
                ) and not _is_under(path, _AGENTS_ROOT):
                    violations.append(
                        _Violation(
                            path=path.relative_to(project_root),
                            lineno=getattr(node, "lineno", 1),
                            message=(
                                f"imports opencode backend package {resolved_module!r} outside agents boundary"
                            ),
                        )
                    )

                for alias in node.names:
                    if alias.name != "start_agent":
                        continue

                    if _is_under(path, _OPENCODE_BACKEND_ROOT):
                        continue

                    if (
                        resolved_module.endswith("opencode.client")
                        or resolved_module.endswith("opencode.backend")
                        or resolved_module.endswith("opencode")
                    ):
                        violations.append(
                            _Violation(
                                path=path.relative_to(project_root),
                                lineno=getattr(node, "lineno", 1),
                                message=f"imports start_agent from {resolved_module!r}",
                            )
                        )

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    if imported.startswith(_LEGACY_OPENCODE_IMPORT_PREFIX):
                        violations.append(
                            _Violation(
                                path=path.relative_to(project_root),
                                lineno=getattr(node, "lineno", 1),
                                message=(
                                    f"imports legacy opencode package {imported!r} (expected {_OPENCODE_BACKEND_IMPORT_PREFIX!r})"
                                ),
                            )
                        )

                    if imported.startswith(
                        _OPENCODE_BACKEND_IMPORT_PREFIX
                    ) and not _is_under(path, _AGENTS_ROOT):
                        violations.append(
                            _Violation(
                                path=path.relative_to(project_root),
                                lineno=getattr(node, "lineno", 1),
                                message=(
                                    f"imports opencode backend package {imported!r} outside agents boundary"
                                ),
                            )
                        )

            if isinstance(node, ast.Attribute) and node.attr == "start_agent":
                if _is_under(path, _OPENCODE_BACKEND_ROOT):
                    continue
                violations.append(
                    _Violation(
                        path=path.relative_to(project_root),
                        lineno=getattr(node, "lineno", 1),
                        message="references attribute start_agent",
                    )
                )

            if isinstance(node, ast.Call):
                if _is_under(path, _OPENCODE_BACKEND_ROOT):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id == "start_agent":
                    violations.append(
                        _Violation(
                            path=path.relative_to(project_root),
                            lineno=getattr(node, "lineno", 1),
                            message="calls start_agent",
                        )
                    )

    return _format_violations(violations)


def main() -> int:
    """Run the agent/OpenCode boundary fitness rule."""
    status = RuleStatus.PASS
    summary = "Agent/OpenCode dependency boundary satisfied."
    violations: list[str] = []

    try:
        violations = _collect_violations(Path("."))
        status = RuleStatus.PASS if not violations else RuleStatus.FAIL
        if status == RuleStatus.FAIL:
            summary = f"Detected {len(violations)} OpenCode boundary violation(s)."
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        status = RuleStatus.ERROR
        summary = f"OpenCode boundary scan failed: {exc}"

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
