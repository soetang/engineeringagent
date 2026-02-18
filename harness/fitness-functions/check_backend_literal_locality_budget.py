from __future__ import annotations

import ast
import re
from pathlib import Path

from engineeringagent.checks import emit_result_envelope
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.backend-literal-locality-budget"
BASELINE_VIOLATION_COUNT = 0

_SOURCE_ROOT = Path("src/engineeringagent")
_ALLOWED_LITERAL_ROOTS = (
    _SOURCE_ROOT / "agents",
    _SOURCE_ROOT / "checks",
)
_TOKENS = (
    "opencode",
    ".opencode",
    "OpenCode",
    "DEFAULT_OPENCODE_AGENT",
    "DEFAULT_OPENCODE_AGENT_MODEL",
)
_TOKEN_SCAN_ORDER = tuple(sorted(_TOKENS, key=lambda token: (-len(token), token)))


def _iter_python_files(project_root: Path) -> list[Path]:
    source_root = project_root / _SOURCE_ROOT
    if not source_root.exists():
        return []
    return sorted(path for path in source_root.rglob("*.py") if path.is_file())


def _is_allowed_literal_path(relative_path: Path) -> bool:
    return any(
        relative_path == allowed_root or allowed_root in relative_path.parents
        for allowed_root in _ALLOWED_LITERAL_ROOTS
    )


def _iter_literal_segments(tree: ast.AST) -> list[tuple[int, str]]:
    segments: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            line = getattr(node, "lineno", 1)
            segments.append((line, node.value))
            continue
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    line = getattr(value, "lineno", getattr(node, "lineno", 1))
                    segments.append((line, value.value))
    return segments


def _token_pattern(token: str) -> re.Pattern[str]:
    prefix = r"(?<![A-Za-z0-9_])" if (token[0].isalnum() or token[0] == "_") else ""
    suffix = r"(?![A-Za-z0-9_])" if (token[-1].isalnum() or token[-1] == "_") else ""
    return re.compile(f"{prefix}{re.escape(token)}{suffix}")


def _collect_violations(project_root: Path) -> list[str]:
    source_root = project_root / _SOURCE_ROOT
    if not source_root.exists():
        return [f"{_SOURCE_ROOT}:1 missing source package root"]

    violations: list[str] = []
    token_patterns = {token: _token_pattern(token) for token in _TOKENS}

    for file_path in _iter_python_files(project_root):
        relative = file_path.relative_to(project_root)
        if _is_allowed_literal_path(relative):
            continue

        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for line, segment in _iter_literal_segments(tree):
            matched_token = next(
                (
                    token
                    for token in _TOKEN_SCAN_ORDER
                    if token_patterns[token].search(segment)
                ),
                None,
            )
            if matched_token is None:
                continue
            violations.append(
                f"{relative}:{line}: backend literal token '{matched_token}' outside agents/checks boundary"
            )

    return sorted(violations)


def main() -> int:
    """Run the backend literal-locality budget fitness rule."""
    status = RuleStatus.PASS
    summary = "Backend literal locality budget satisfied."
    violations: list[str] = []

    try:
        violations = _collect_violations(Path("."))
        observed_count = len(violations)
        baseline_count = BASELINE_VIOLATION_COUNT
        if observed_count > baseline_count:
            status = RuleStatus.FAIL
            summary = (
                "Backend literal locality budget exceeded "
                f"(observed={observed_count}, baseline={baseline_count})."
            )
        else:
            summary = (
                "Backend literal locality budget satisfied "
                f"(observed={observed_count}, baseline={baseline_count})."
            )
    except (OSError, SyntaxError, UnicodeError, ValueError) as exc:
        status = RuleStatus.ERROR
        summary = f"Backend literal locality scan failed: {exc}"
        observed_count = 0
        baseline_count = BASELINE_VIOLATION_COUNT

    emit_result_envelope(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=RULE_ID,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
            details={
                "baseline_violation_count": baseline_count,
                "observed_violation_count": observed_count,
                "tokens": list(_TOKENS),
            },
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
