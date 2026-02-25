from __future__ import annotations

from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


def build_boundary_rule_result(
    *,
    rule_id: str,
    violations: list[str],
    pass_summary: str,
    fail_summary_label: str,
) -> FitnessRuleResult:
    """Build a deterministic boundary-rule result envelope payload."""

    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        pass_summary
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} {fail_summary_label} violation(s)."
    )
    return FitnessRuleResult(
        contract_version=CONTRACT_VERSION,
        rule_id=rule_id,
        status=status,
        severity=RuleSeverity.ERROR,
        summary=summary,
        violations=violations,
    )
