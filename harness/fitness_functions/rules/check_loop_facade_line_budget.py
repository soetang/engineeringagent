from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.loop-facade-line-budget"
BASELINE_LINE_COUNT = 1436
MAX_LINE_BUDGET = 650


def main() -> int:
    """Run the loop facade line-budget fitness rule."""
    loop_path = Path("src/engineeringagent/loop.py")
    if not loop_path.exists():
        emit_fitness_result(
            FitnessRuleResult(
                contract_version=CONTRACT_VERSION,
                rule_id=RULE_ID,
                status=RuleStatus.PASS,
                severity=RuleSeverity.ERROR,
                summary="Loop facade is absent; legacy line budget is retired.",
                violations=[],
            )
        )
        return 0

    lines = len(loop_path.read_text(encoding="utf-8").splitlines())

    violations: list[str] = []
    if lines >= BASELINE_LINE_COUNT:
        violations.append(
            "src/engineeringagent/loop.py line count must stay below "
            f"{BASELINE_LINE_COUNT}; current={lines}"
        )
    if lines > MAX_LINE_BUDGET:
        violations.append(
            "src/engineeringagent/loop.py line count must be <= "
            f"{MAX_LINE_BUDGET}; current={lines}"
        )

    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        f"loop facade line budget satisfied at {lines} lines."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} loop facade line-budget violation(s)."
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
