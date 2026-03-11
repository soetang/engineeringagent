from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.legacy-run-loop-bridge-absent"
_REMOVED_PATHS = (
    Path("src/engineeringagent/adapters/loop/__init__.py"),
    Path("src/engineeringagent/adapters/loop/runtime_feature_iteration_executor.py"),
    Path("src/engineeringagent/adapters/loop/legacy_run_loop_executor.py"),
    Path("src/engineeringagent/adapters/loop/runtime_run_loop_executor.py"),
)
_REMEDIATION = (
    "keep runtime loop execution wiring under engineeringagent.bootstrap.runtime_execution "
    "and do not restore the deleted engineeringagent.adapters.loop package."
)


def main() -> int:
    """Fail if removed legacy run-loop bridge paths reappear."""
    violations = [
        f"{path}: deleted legacy run-loop bridge path must remain absent; {_REMEDIATION}"
        for path in _REMOVED_PATHS
        if path.exists()
    ]
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Legacy run-loop bridge module names remain absent."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} legacy run-loop bridge path violation(s)."
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
