from __future__ import annotations

from pathlib import Path

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)
from engineeringagent.fitness.envelope import emit_result_envelope


RULE_ID = "architecture.harness-root-yaml-only"
HARNESS_ROOT = Path("harness")
ALLOWED_EXTENSIONS = {".yaml", ".yml"}
REMEDIATION = (
    "move executable/policy files under harness/fitness-functions or another harness "
    "subdirectory."
)


def _violations_for_harness_root_files() -> list[str]:
    if not HARNESS_ROOT.is_dir():
        return []

    violations: list[str] = []
    for path in sorted(HARNESS_ROOT.iterdir(), key=lambda candidate: candidate.name):
        if not path.is_file():
            continue
        if _is_allowed_manifest(path):
            continue
        violations.append(
            f"{path.as_posix()}:1 non-YAML regular file at harness root; {REMEDIATION}"
        )
    return violations


def _is_allowed_manifest(path: Path) -> bool:
    return path.suffix.lower() in ALLOWED_EXTENSIONS


def main() -> int:
    """Enforce a YAML-only regular-file contract for harness root."""
    violations = _violations_for_harness_root_files()
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Harness root contains only YAML manifest files."
        if status == RuleStatus.PASS
        else "Detected non-YAML regular files at harness root."
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
