from __future__ import annotations

import argparse
import io
import re
import tokenize
from pathlib import Path

from engineeringagent.checks import emit_result_envelope
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


DEFAULT_RULE_ID = "architecture.no-non-ignorable-ruff-suppressions"
DEFAULT_SCAN_ROOTS = ("src", "tests", "harness")

INLINE_NOQA_RE = re.compile(
    r"#\s*noqa(?:\s*:\s*([A-Za-z0-9]+(?:\s*,\s*[A-Za-z0-9]+)*))?",
    re.IGNORECASE,
)
RUFF_FILE_NOQA_RE = re.compile(
    r"#\s*ruff:\s*noqa(?:\s*:\s*([A-Za-z0-9]+(?:\s*,\s*[A-Za-z0-9]+)*))?",
    re.IGNORECASE,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule-id", default=DEFAULT_RULE_ID)
    parser.add_argument(
        "--blocked-rule-id",
        dest="blocked_rule_ids",
        action="append",
        required=True,
    )
    parser.add_argument(
        "--scan-root",
        dest="scan_roots",
        action="append",
        default=None,
    )
    return parser.parse_args()


def _parse_codes(match: re.Match[str]) -> set[str] | None:
    group = match.group(1)
    if group is None:
        return None
    return {code.strip().upper() for code in group.split(",") if code.strip()}


def _matching_codes(comment: str, blocked_rule_ids: set[str]) -> set[str] | None:
    ruff_match = RUFF_FILE_NOQA_RE.search(comment)
    if ruff_match is not None:
        parsed = _parse_codes(ruff_match)
        if parsed is None:
            return None
        return parsed & blocked_rule_ids

    inline_match = INLINE_NOQA_RE.search(comment)
    if inline_match is None:
        return set()
    parsed = _parse_codes(inline_match)
    if parsed is None:
        return None
    return parsed & blocked_rule_ids


def _iter_python_files(scan_roots: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for raw_root in scan_roots:
        root = Path(raw_root)
        if root.is_file() and root.suffix == ".py":
            files.append(root)
            continue
        if root.is_dir():
            files.extend(root.rglob("*.py"))
    return sorted(set(files))


def _scan_file(path: Path, blocked_rule_ids: set[str]) -> list[str]:
    source = path.read_text(encoding="utf-8")
    violations: list[str] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type != tokenize.COMMENT:
                continue

            matched_codes = _matching_codes(token.string, blocked_rule_ids)
            if matched_codes == set():
                continue

            line = token.start[0]
            column = token.start[1] + 1
            location = f"{path.as_posix()}:{line}:{column}"

            if matched_codes is None:
                target_text = "ALL"
            else:
                target_text = ",".join(sorted(matched_codes))

            violations.append(
                (
                    f"{location} non-ignorable Ruff suppression detected"
                    f" (targets: {target_text}); remove suppression comments and"
                    " refactor. For PLR0913, group related parameters into a"
                    " NamedTuple or pydantic model."
                )
            )
    except tokenize.TokenError as exc:
        violations.append(
            f"{path.as_posix()}:1:1 unable to tokenize file while scanning suppressions: {exc}"
        )

    return violations


def main() -> int:
    args = _parse_args()
    blocked_rule_ids = {rule_id.upper() for rule_id in args.blocked_rule_ids}
    scan_roots = (
        tuple(args.scan_roots) if args.scan_roots is not None else DEFAULT_SCAN_ROOTS
    )

    files = _iter_python_files(scan_roots)
    violations: list[str] = []
    for file_path in files:
        violations.extend(_scan_file(file_path, blocked_rule_ids))

    violations = sorted(set(violations))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL

    summary = (
        "No non-ignorable Ruff suppressions detected under configured scan roots."
        if status == RuleStatus.PASS
        else (
            "Detected non-ignorable Ruff suppressions. Remove inline/file-level "
            "ignore directives and refactor code (for PLR0913, prefer structured "
            "parameter objects such as NamedTuple or pydantic models)."
        )
    )

    emit_result_envelope(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=args.rule_id,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
