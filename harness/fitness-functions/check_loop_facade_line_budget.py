from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
    emit_result_envelope,
)


RULE_ID = "architecture.loop-facade-line-budget"
BASELINE_LINE_COUNT = 1436
MAX_LINE_BUDGET = 650


def main() -> int:
    loop_path = Path("src/engineeringagent/loop.py")
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
    return 0 if status == RuleStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
