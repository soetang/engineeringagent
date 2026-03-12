from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.adapter-root-locality"
_ADAPTERS_ROOT = Path("src/engineeringagent/adapters")
_REMEDIATION = (
    "move root-level adapter implementation files into a focused subpackage under "
    "engineeringagent.adapters/."
)


def _collect_violations(project_root: Path) -> list[str]:
    adapters_root = project_root / _ADAPTERS_ROOT
    if not adapters_root.exists():
        return [f"missing adapters package root: {_ADAPTERS_ROOT}"]

    violations: list[str] = []
    for path in sorted(adapters_root.glob("*.py")):
        if path.name == "__init__.py":
            continue
        relative_path = path.relative_to(project_root).as_posix()
        violations.append(
            f"{relative_path}: root-level adapter module is not allowed; {_REMEDIATION}"
        )
    return violations


def main() -> int:
    """Run the adapter root-locality fitness rule."""
    violations = _collect_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Adapter implementations are localized to focused adapters subpackages."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} root-level adapter module violation(s)."
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
