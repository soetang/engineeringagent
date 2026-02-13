from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleMetadata,
    RuleAdapter,
    RuleSeverity,
    RuleSource,
)
from engineeringagent.fitness.registry import FitnessRuleDefinition, build_rule_catalog


def _builtin_definition(rule_id: str) -> FitnessRuleDefinition:
    return FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id=rule_id,
            name=f"Built-in {rule_id}",
            summary="Built-in collision test rule.",
            rationale="Registry must fail fast on duplicate IDs.",
            remediation="Rename the duplicate rule IDs.",
            scope="src/engineeringagent",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.PYTHON,
            source=RuleSource.BUILTIN,
            side_effect_free=True,
        ),
        origin=f"builtin:{rule_id}",
    )


def _write_manifest(path: Path, rules: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"contract_version": CONTRACT_VERSION, "rules": rules},
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def test_duplicate_rule_ids_across_builtin_and_custom_sources_fail_fast(
    tmp_path: Path,
) -> None:
    """Raise actionable errors when declared builtin and custom IDs collide."""
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            {"builtin": "architecture.dep-direction"},
            {
                "rule_id": "architecture.dep-direction",
                "name": "Custom architecture.dep-direction",
                "summary": "Custom collision test rule.",
                "rationale": "Exercise duplicate detection.",
                "remediation": "Rename manifest rule IDs.",
                "scope": "docs",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "command": ["python", "scripts/custom_rule.py"],
            },
        ],
    )

    with pytest.raises(ValueError) as excinfo:
        build_rule_catalog(
            tmp_path,
            builtin_rules=[_builtin_definition("architecture.dep-direction")],
        )

    message = str(excinfo.value)
    assert "duplicate fitness rule_id detected" in message
    assert "architecture.dep-direction" in message
    assert "builtin-ref:" in message
    assert "custom:" in message


def test_duplicate_rule_ids_within_custom_manifest_fail_fast(tmp_path: Path) -> None:
    """Raise actionable errors when custom manifest IDs collide."""
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            {
                "rule_id": "custom.docs-links",
                "name": "Custom custom.docs-links",
                "summary": "Custom collision test rule.",
                "rationale": "Exercise duplicate detection.",
                "remediation": "Rename manifest rule IDs.",
                "scope": "docs",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "command": ["python", "scripts/custom_rule.py"],
            },
            {
                "rule_id": "custom.docs-links",
                "name": "Custom custom.docs-links again",
                "summary": "Custom collision test rule.",
                "rationale": "Exercise duplicate detection.",
                "remediation": "Rename manifest rule IDs.",
                "scope": "docs",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "command": ["python", "scripts/custom_rule.py"],
            },
        ],
    )

    with pytest.raises(ValueError) as excinfo:
        build_rule_catalog(tmp_path, builtin_rules=[])

    message = str(excinfo.value)
    assert "duplicate fitness rule_id detected" in message
    assert "custom.docs-links" in message
    assert "rules[0]" in message
    assert "rules[1]" in message
