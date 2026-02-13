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


def _write_manifest(path: Path, rules: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "contract_version": CONTRACT_VERSION,
                "rules": rules,
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def test_build_rule_catalog_includes_only_manifest_declared_rules_sorted_by_id(
    tmp_path: Path,
) -> None:
    """Resolve builtins by manifest reference and keep deterministic ordering."""
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            {"builtin": "builtin.z-last"},
            {
                "rule_id": "custom.middle",
                "name": "Custom rule",
                "summary": "Custom command rule.",
                "rationale": "Exercise manifest-driven registry behavior.",
                "remediation": "Update custom rules manifest.",
                "scope": "docs",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "command": ["python", "scripts/custom_rule.py"],
            },
        ],
    )

    catalog = build_rule_catalog(
        tmp_path,
        builtin_rules=[
            _builtin_definition("builtin.z-last"),
            _builtin_definition("builtin.a-first"),
        ],
    )

    assert [definition.metadata.rule_id for definition in catalog] == [
        "builtin.z-last",
        "custom.middle",
    ]


def test_build_rule_catalog_returns_empty_when_manifest_is_missing(
    tmp_path: Path,
) -> None:
    """Do not activate implicit built-ins without a manifest declaration."""
    catalog = build_rule_catalog(
        tmp_path,
        builtin_rules=[_builtin_definition("builtin.a-first")],
    )

    assert catalog == []
