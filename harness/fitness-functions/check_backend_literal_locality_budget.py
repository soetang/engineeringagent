from __future__ import annotations

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
_DETAIL_TOKENS = tuple(sorted(_TOKENS))
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


def _token_pattern(token: str) -> re.Pattern[str]:
    prefix = r"(?<![A-Za-z0-9_])" if (token[0].isalnum() or token[0] == "_") else ""
    suffix = r"(?![A-Za-z0-9_])" if (token[-1].isalnum() or token[-1] == "_") else ""
    return re.compile(f"{prefix}{re.escape(token)}{suffix}")


def _match_line_token(
    line: str,
    *,
    token_patterns: dict[str, re.Pattern[str]],
) -> str | None:
    return next(
        (token for token in _TOKEN_SCAN_ORDER if token_patterns[token].search(line)),
        None,
    )


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

        for line_number, line in enumerate(
            file_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            matched_token = _match_line_token(line, token_patterns=token_patterns)
            if matched_token is None:
                continue
            violations.append(
                f"{relative}:{line_number}: backend literal token '{matched_token}' outside agents/checks boundary"
            )

    return sorted(violations)


def _baseline_refresh_metadata(
    *,
    baseline_count: int,
    observed_count: int,
) -> tuple[bool, int, int]:
    refresh_recommended = observed_count <= baseline_count
    refresh_target = observed_count if refresh_recommended else baseline_count
    refresh_delta = refresh_target - baseline_count
    return refresh_recommended, refresh_target, refresh_delta


def main() -> int:
    """Run the backend literal-locality budget fitness rule."""
    status = RuleStatus.PASS
    summary = "Backend literal locality budget satisfied."
    violations: list[str] = []

    try:
        violations = _collect_violations(Path("."))
        observed_count = len(violations)
        baseline_count = BASELINE_VIOLATION_COUNT
        refresh_recommended, refresh_target, refresh_delta = _baseline_refresh_metadata(
            baseline_count=baseline_count,
            observed_count=observed_count,
        )
        if observed_count > baseline_count:
            status = RuleStatus.FAIL
            summary = (
                "Backend literal locality budget exceeded "
                f"(observed={observed_count}, baseline={baseline_count}, "
                f"refresh_target={refresh_target}; do not raise baseline)."
            )
        else:
            summary = (
                "Backend literal locality budget satisfied "
                f"(observed={observed_count}, baseline={baseline_count}, "
                f"refresh_target={refresh_target})."
            )
    except (OSError, UnicodeError, ValueError) as exc:
        status = RuleStatus.ERROR
        summary = f"Backend literal locality scan failed: {exc}"
        observed_count = 0
        baseline_count = BASELINE_VIOLATION_COUNT
        refresh_recommended, refresh_target, refresh_delta = _baseline_refresh_metadata(
            baseline_count=baseline_count,
            observed_count=observed_count,
        )

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
                "baseline_refresh_recommended": refresh_recommended,
                "baseline_refresh_target_violation_count": refresh_target,
                "baseline_refresh_delta": refresh_delta,
                "tokens": list(_DETAIL_TOKENS),
            },
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
