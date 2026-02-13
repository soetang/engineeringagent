from __future__ import annotations

from pathlib import Path

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
            summary="Built-in rule for registry ordering tests.",
            rationale="Registry ordering must be deterministic.",
            remediation="Adjust rule inventory definitions.",
            scope="src/engineeringagent",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.PYTHON,
            source=RuleSource.BUILTIN,
            side_effect_free=True,
        ),
        origin=f"builtin:{rule_id}",
    )


def _write_custom_manifest(path: Path, rule_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "contract_version": CONTRACT_VERSION,
                "rules": [
                    {
                        "rule_id": rule_id,
                        "name": "Custom rule",
                        "summary": "Custom command rule.",
                        "rationale": "Exercise merged registry behavior.",
                        "remediation": "Update custom rules manifest.",
                        "scope": "docs",
                        "severity": "warning",
                        "side_effect_free": True,
                        "adapter": "command",
                        "command": ["python", "scripts/custom_rule.py"],
                    }
                ],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def test_build_rule_catalog_merges_builtin_and_custom_rules_sorted_by_id(
    tmp_path: Path,
) -> None:
    """Merge built-in and custom rules with deterministic ordering by ID."""
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_custom_manifest(manifest_path, "custom.middle")

    catalog = build_rule_catalog(
        tmp_path,
        builtin_rules=[
            _builtin_definition("builtin.z-last"),
            _builtin_definition("builtin.a-first"),
        ],
    )

    assert [definition.metadata.rule_id for definition in catalog] == [
        "builtin.a-first",
        "builtin.z-last",
        "custom.middle",
    ]
