from __future__ import annotations

import argparse
import io
import re
import tokenize
from pathlib import Path
from typing import Any

import yaml

from engineeringagent.adapters.quality.fitness import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
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


class _RuntimePolicyError(ValueError):
    def __init__(self, *, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule-id", default=None)
    parser.add_argument(
        "--blocked-rule-id",
        dest="blocked_rule_ids",
        action="append",
        default=None,
    )
    parser.add_argument(
        "--scan-root",
        dest="scan_roots",
        action="append",
        default=None,
    )
    parser.add_argument(
        "--config-file",
        dest="config_file",
        default=None,
    )
    return parser.parse_args()


def _load_policy_config(config_file: str | None) -> dict[str, Any]:
    if config_file is None:
        return {}

    policy_path = Path(config_file)
    try:
        payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"unable to read config file {policy_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"unable to parse config file {policy_path}: {exc}") from exc

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"config file must contain a YAML mapping: {policy_path}")
    return payload


def _config_string(policy: dict[str, Any], key: str) -> str | None:
    value = policy.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"config key '{key}' must be a non-empty string")
    return value.strip()


def _config_string_list(policy: dict[str, Any], key: str) -> tuple[str, ...] | None:
    value = policy.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"config key '{key}' must be a list of non-empty strings")

    parsed: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"config key '{key}' must be a list of non-empty strings")
        parsed.append(item.strip())

    return tuple(parsed)


def _resolve_runtime_config(
    args: argparse.Namespace,
    *,
    policy: dict[str, Any],
) -> tuple[set[str], tuple[str, ...]]:
    blocked_values = (
        tuple(args.blocked_rule_ids)
        if args.blocked_rule_ids is not None
        else _config_string_list(policy, "blocked_rule_ids")
    )
    if not blocked_values:
        raise ValueError(
            "missing blocked rule IDs: use --blocked-rule-id or provide "
            "'blocked_rule_ids' in config file"
        )

    scan_roots = (
        tuple(args.scan_roots)
        if args.scan_roots is not None
        else _config_string_list(policy, "scan_roots") or DEFAULT_SCAN_ROOTS
    )

    blocked_rule_ids = {blocked_id.upper() for blocked_id in blocked_values}
    return blocked_rule_ids, scan_roots


def _resolve_runtime_policy(
    args: argparse.Namespace,
) -> tuple[str, set[str], tuple[str, ...]]:
    fallback_rule_id = args.rule_id or DEFAULT_RULE_ID
    try:
        policy = _load_policy_config(args.config_file)
    except ValueError as exc:
        raise _RuntimePolicyError(rule_id=fallback_rule_id, message=str(exc)) from exc

    rule_id = fallback_rule_id
    try:
        rule_id = args.rule_id or _config_string(policy, "rule_id") or DEFAULT_RULE_ID
        blocked_rule_ids, scan_roots = _resolve_runtime_config(args, policy=policy)
    except ValueError as exc:
        raise _RuntimePolicyError(rule_id=rule_id, message=str(exc)) from exc

    return rule_id, blocked_rule_ids, scan_roots


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
    """Run the non-ignorable Ruff suppression scan fitness rule."""
    args = _parse_args()
    try:
        rule_id, blocked_rule_ids, scan_roots = _resolve_runtime_policy(args)
    except _RuntimePolicyError as exc:
        emit_fitness_result(
            FitnessRuleResult(
                contract_version=CONTRACT_VERSION,
                rule_id=exc.rule_id,
                status=RuleStatus.ERROR,
                severity=RuleSeverity.ERROR,
                summary=f"Invalid Ruff suppression policy configuration: {exc}",
                violations=[],
            )
        )
        return 0

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

    emit_fitness_result(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=rule_id,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
