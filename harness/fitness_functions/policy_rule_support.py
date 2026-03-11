from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import yaml

from engineeringagent.checks import emit_fitness_result
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)

YamlPolicyLoader = Callable[[Path], dict[str, Any]]
PolicyRuleEvaluator = Callable[[Path, Path], list[str]]
PolicyRuleFailureSummary = Callable[[int], str]


class PolicyRuleRunner(Protocol):
    """Callable contract for the shared policy-backed checker entrypoint."""

    def __call__(
        self,
        *,
        rule_id: str,
        default_policy: Path,
        pass_summary: str,
        fail_summary: PolicyRuleFailureSummary,
        error_summary_prefix: str,
        evaluate: PolicyRuleEvaluator,
    ) -> int: ...
def parse_policy_args(default_policy: Path) -> argparse.Namespace:
    """Parse the shared `--config-file` CLI flag for policy-backed checkers."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", default=str(default_policy))
    return parser.parse_args()


def resolve_policy_file(path_value: str) -> Path:
    """Validate and return the policy file path passed through the CLI."""
    config_file = Path(path_value)
    if not config_file.is_file():
        raise ValueError(f"policy config not found: {config_file}")
    return config_file


def load_yaml_policy(config_file: Path) -> dict[str, Any]:
    """Load a YAML policy file and require the root payload to be a mapping."""
    try:
        payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"failed to read policy config: {config_file}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"policy config is not valid YAML: {config_file}") from exc

    if not isinstance(payload, dict):
        raise ValueError("policy config must be a mapping")
    return payload
def run_policy_rule(
    *,
    rule_id: str,
    default_policy: Path,
    pass_summary: str,
    fail_summary: PolicyRuleFailureSummary,
    error_summary_prefix: str,
    evaluate: PolicyRuleEvaluator,
) -> int:
    """Execute a policy-backed fitness rule and emit the contract payload."""
    args = parse_policy_args(default_policy)
    violations: list[str] = []
    status = RuleStatus.PASS
    summary = pass_summary

    try:
        config_file = resolve_policy_file(args.config_file)
        violations = evaluate(Path("."), config_file)
        if violations:
            status = RuleStatus.FAIL
            summary = fail_summary(len(violations))
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        status = RuleStatus.ERROR
        summary = f"{error_summary_prefix}: {exc}"

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
