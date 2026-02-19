from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

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
_DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parent
    / "policies"
    / "backend_literal_locality_budget.yaml"
)


class _RuntimePolicyError(ValueError):
    pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", dest="config_file", default=None)
    return parser.parse_args()


def _load_policy(config_file: str | None) -> dict[str, Any]:
    policy_path = Path(config_file) if config_file is not None else _DEFAULT_POLICY_PATH
    try:
        payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _RuntimePolicyError(
            f"unable to read config file {policy_path}: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise _RuntimePolicyError(
            f"unable to parse config file {policy_path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise _RuntimePolicyError("config file must contain a YAML mapping")
    return payload


def _config_string(policy: dict[str, Any], key: str) -> str:
    value = policy.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _RuntimePolicyError(f"config key '{key}' must be a non-empty string")
    return value.strip()


def _config_string_list(policy: dict[str, Any], key: str) -> tuple[str, ...]:
    value = policy.get(key)
    error = f"config key '{key}' must be a non-empty list of strings"
    if not isinstance(value, list) or not value:
        raise _RuntimePolicyError(error)

    parsed: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise _RuntimePolicyError(error)
        parsed.append(item.strip())
    return tuple(parsed)


def _parse_backend_tokens(policy: dict[str, Any]) -> tuple[str, ...]:
    raw_backends = policy.get("backends")
    if not isinstance(raw_backends, dict) or not raw_backends:
        raise _RuntimePolicyError("config key 'backends' must be a non-empty mapping")

    all_tokens: set[str] = set()
    for backend_id, backend_config in raw_backends.items():
        if not isinstance(backend_id, str) or not backend_id.strip():
            raise _RuntimePolicyError(
                "config key 'backends' must use non-empty backend id keys"
            )
        if not isinstance(backend_config, dict):
            raise _RuntimePolicyError(
                f"backend '{backend_id}' configuration must be a mapping"
            )
        tokens = _config_string_list(backend_config, "tokens")
        all_tokens.update(tokens)

    if not all_tokens:
        raise _RuntimePolicyError(
            "config key 'backends' must define at least one token"
        )

    return tuple(sorted(all_tokens))


def _resolve_policy(
    config_file: str | None,
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    policy = _load_policy(config_file)
    policy_rule_id = _config_string(policy, "rule_id")
    if policy_rule_id != RULE_ID:
        raise _RuntimePolicyError(f"rule_id must match {RULE_ID}: {policy_rule_id!r}")

    allowed_root_strings = _config_string_list(policy, "allowed_literal_roots")
    allowed_roots = tuple(Path(root) for root in allowed_root_strings)
    tokens = _parse_backend_tokens(policy)
    return allowed_roots, tokens


def _iter_python_files(project_root: Path) -> list[Path]:
    source_root = project_root / _SOURCE_ROOT
    if not source_root.exists():
        return []
    return sorted(path for path in source_root.rglob("*.py") if path.is_file())


def _is_allowed_literal_path(
    relative_path: Path,
    *,
    allowed_literal_roots: tuple[Path, ...],
) -> bool:
    return any(
        relative_path == allowed_root or allowed_root in relative_path.parents
        for allowed_root in allowed_literal_roots
    )


def _token_pattern(token: str) -> re.Pattern[str]:
    prefix = r"(?<![A-Za-z0-9_])" if (token[0].isalnum() or token[0] == "_") else ""
    suffix = r"(?![A-Za-z0-9_])" if (token[-1].isalnum() or token[-1] == "_") else ""
    return re.compile(f"{prefix}{re.escape(token)}{suffix}")


def _match_line_token(
    line: str,
    *,
    token_scan_order: tuple[str, ...],
    token_patterns: dict[str, re.Pattern[str]],
) -> str | None:
    return next(
        (token for token in token_scan_order if token_patterns[token].search(line)),
        None,
    )


def _collect_violations(
    project_root: Path,
    *,
    allowed_literal_roots: tuple[Path, ...],
    tokens: tuple[str, ...],
) -> list[str]:
    source_root = project_root / _SOURCE_ROOT
    if not source_root.exists():
        return [f"{_SOURCE_ROOT}:1 missing source package root"]

    violations: list[str] = []
    token_patterns = {token: _token_pattern(token) for token in tokens}
    token_scan_order = tuple(sorted(tokens, key=lambda token: (-len(token), token)))

    for file_path in _iter_python_files(project_root):
        relative = file_path.relative_to(project_root)
        if _is_allowed_literal_path(
            relative,
            allowed_literal_roots=allowed_literal_roots,
        ):
            continue

        for line_number, line in enumerate(
            file_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            matched_token = _match_line_token(
                line,
                token_scan_order=token_scan_order,
                token_patterns=token_patterns,
            )
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


def _error_baseline_state() -> tuple[int, int, bool, int, int]:
    baseline_count = BASELINE_VIOLATION_COUNT
    observed_count = 0
    refresh_recommended, refresh_target, refresh_delta = _baseline_refresh_metadata(
        baseline_count=baseline_count,
        observed_count=observed_count,
    )
    return (
        baseline_count,
        observed_count,
        refresh_recommended,
        refresh_target,
        refresh_delta,
    )


def main() -> int:
    """Run the backend literal-locality budget fitness rule."""
    args = _parse_args()
    status = RuleStatus.PASS
    summary = "Backend literal locality budget satisfied."
    violations: list[str] = []
    detail_tokens: tuple[str, ...] = ()

    try:
        allowed_literal_roots, tokens = _resolve_policy(args.config_file)
        detail_tokens = tokens
        violations = _collect_violations(
            Path("."),
            allowed_literal_roots=allowed_literal_roots,
            tokens=tokens,
        )
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
    except _RuntimePolicyError as exc:
        status = RuleStatus.ERROR
        summary = f"Invalid backend literal locality policy configuration: {exc}"
        (
            baseline_count,
            observed_count,
            refresh_recommended,
            refresh_target,
            refresh_delta,
        ) = _error_baseline_state()
    except (OSError, UnicodeError, ValueError) as exc:
        status = RuleStatus.ERROR
        summary = f"Backend literal locality scan failed: {exc}"
        (
            baseline_count,
            observed_count,
            refresh_recommended,
            refresh_target,
            refresh_delta,
        ) = _error_baseline_state()

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
                "tokens": list(detail_tokens),
            },
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
