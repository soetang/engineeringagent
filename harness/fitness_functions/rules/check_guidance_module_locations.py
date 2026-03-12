from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.guidance-module-locations"
_REQUIRED_PATHS = (
    Path("src/engineeringagent/adapters/documents/filesystem_guidance_topic_repository.py"),
    Path("src/engineeringagent/presentation/cli/guidance.py"),
)
_LEGACY_PATHS = (
    Path("src/engineeringagent/approach/__init__.py"),
    Path("src/engineeringagent/approach/registry.py"),
    Path("src/engineeringagent/approach/rendering.py"),
    Path("src/engineeringagent/adapters/guidance/__init__.py"),
    Path(
        "src/engineeringagent/adapters/guidance/filesystem_guidance_topic_repository.py"
    ),
    Path("src/engineeringagent/adapters/documents/packaged_guidance_topic_repository.py"),
    Path("src/engineeringagent/presentation/cli/approach.py"),
)
_REMEDIATION = (
    "keep guidance-topic repositories under engineeringagent.adapters.documents and the CLI "
    "surface under engineeringagent.presentation.cli.guidance; do not restore the "
    "legacy engineeringagent.approach package, packaged-guidance module, "
    "adapters.guidance package, or presentation.cli.approach module."
)


def _collect_violations(project_root: Path) -> list[str]:
    violations: list[str] = []
    for required_path in _REQUIRED_PATHS:
        if (project_root / required_path).is_file():
            continue
        violations.append(
            f"{required_path.as_posix()}: required guidance architecture path is "
            f"missing; {_REMEDIATION}"
        )
    for legacy_path in _LEGACY_PATHS:
        if not (project_root / legacy_path).exists():
            continue
        violations.append(
            f"{legacy_path.as_posix()}: legacy guidance architecture path is not "
            f"allowed; {_REMEDIATION}"
        )
    return violations


def main() -> int:
    """Run the guidance-module-locations fitness rule."""
    violations = _collect_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Guidance modules are localized to the target architecture paths."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} guidance module location violation(s)."
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
