from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.repo-config-presence"
CONFIG_PATH = Path("engineeringagent.toml")
_REMEDIATION = (
    "commit engineeringagent.toml at the repository root and keep it as the canonical "
    "repository configuration surface; use pyproject.toml only as a fallback for "
    "repositories that have not adopted the dedicated config file yet."
)


def main() -> int:
    """Fail when the repository is missing the canonical config file."""
    violations = []
    if not CONFIG_PATH.is_file():
        violations.append(
            f"{CONFIG_PATH}: canonical repository config file is missing; {_REMEDIATION}"
        )

    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Canonical repository config file is present."
        if status == RuleStatus.PASS
        else "Canonical repository config file is missing."
    )
    emit_fitness_result(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=RULE_ID,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
        )
    )
    return 0 if status == RuleStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
