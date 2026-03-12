from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)
from engineeringagent.checks import emit_fitness_result


RULE_ID = "architecture.init-cli-support-location"
_REQUIRED_PATHS = (Path("src/engineeringagent/bootstrap/init_cli_support.py"),)
_LEGACY_PATHS = (Path("src/engineeringagent/init_cli_support.py"),)
_REMEDIATION = (
    "keep init CLI support wiring under engineeringagent.bootstrap; "
    "do not restore the root-level engineeringagent.init_cli_support module."
)


def _collect_violations(project_root: Path) -> list[str]:
    violations: list[str] = []
    for required_path in _REQUIRED_PATHS:
        if (project_root / required_path).is_file():
            continue
        violations.append(
            f"{required_path.as_posix()}: required init CLI support module path is "
            f"missing; {_REMEDIATION}"
        )
    for legacy_path in _LEGACY_PATHS:
        if not (project_root / legacy_path).exists():
            continue
        violations.append(
            f"{legacy_path.as_posix()}: legacy init CLI support module path is not "
            f"allowed; {_REMEDIATION}"
        )
    return violations


def main() -> int:
    """Run the init-cli-support-location fitness rule."""
    violations = _collect_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Init CLI support is localized to engineeringagent.bootstrap."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} init CLI support location violation(s)."
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
