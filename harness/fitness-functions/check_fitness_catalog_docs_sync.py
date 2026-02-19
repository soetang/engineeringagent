from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import emit_result_envelope, render_fitness_catalog
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.fitness-catalog-docs-sync"
_CATALOG_DOC_PATH = Path("docs/fitness-functions/rules.md")
_REMEDIATION_COMMAND = (
    "uv run engineeringagent checks catalog --format markdown --output "
    "docs/fitness-functions/rules.md"
)


def _expected_catalog_bytes(project_root: Path) -> bytes:
    rendered = render_fitness_catalog(project_root, format="markdown")
    return (rendered + "\n").encode("utf-8")


def _catalog_docs_sync_violations(project_root: Path) -> list[str]:
    catalog_path = project_root / _CATALOG_DOC_PATH
    if not catalog_path.exists() or not catalog_path.is_file():
        return [
            f"{_CATALOG_DOC_PATH}:1 missing file; regenerate with `{_REMEDIATION_COMMAND}`."
        ]

    expected = _expected_catalog_bytes(project_root)
    actual = catalog_path.read_bytes()
    if actual == expected:
        return []

    return [
        f"{_CATALOG_DOC_PATH}:1 differs from `uv run engineeringagent checks catalog --format markdown` output; regenerate with `{_REMEDIATION_COMMAND}`."
    ]


def main() -> int:
    """Run the fitness catalog docs sync check and emit a result envelope."""
    violations = _catalog_docs_sync_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Fitness catalog markdown docs are byte-aligned with catalog output."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} fitness catalog docs sync violation(s)."
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
