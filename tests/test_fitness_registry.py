from __future__ import annotations

from pathlib import Path

import yaml

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    RuleSeverity,
    RuleAdapter,
)
from engineeringagent.fitness.registry import build_rule_catalog


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
    """Load only manifest entries and keep deterministic rule-id ordering."""
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            {
                "rule_id": "custom.z-last",
                "name": "Custom z-last",
                "summary": "Custom command rule z-last.",
                "rationale": "Exercise manifest-driven registry behavior.",
                "remediation": "Update custom rules manifest.",
                "scope": "docs",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "command": ["python", "scripts/custom_rule.py"],
            },
            {
                "rule_id": "custom.a-first",
                "name": "Custom a-first",
                "summary": "Custom command rule a-first.",
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

    catalog = build_rule_catalog(tmp_path)

    assert [definition.metadata.rule_id for definition in catalog] == [
        "custom.a-first",
        "custom.z-last",
    ]


def test_build_rule_catalog_returns_empty_when_manifest_is_missing(
    tmp_path: Path,
) -> None:
    """Do not activate implicit rules without a manifest declaration."""
    catalog = build_rule_catalog(tmp_path)

    assert catalog == []


def test_default_manifest_keeps_loop_boundary_as_error_command_rule() -> None:
    """Keep loop subprocess boundary wired as blocking command-adapter policy."""
    project_root = Path(__file__).resolve().parents[1]

    catalog = build_rule_catalog(project_root)
    definition = next(
        item
        for item in catalog
        if item.metadata.rule_id == "architecture.loop-subprocess-boundary"
    )

    assert definition.metadata.adapter == RuleAdapter.COMMAND
    assert definition.metadata.severity == RuleSeverity.ERROR
    assert definition.command == (
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_loop_subprocess_boundary.py",
    )
