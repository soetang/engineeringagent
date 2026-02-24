from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    RuleAdapter,
    RuleSeverity,
)
from engineeringagent.checks.fitness.registry import build_rule_catalog


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

    assert not catalog


def test_build_rule_catalog_parses_error_severity_and_command_tuple(
    tmp_path: Path,
) -> None:
    """Parse error severity and preserve manifest command list ordering."""
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            {
                "rule_id": "architecture.loop-subprocess-boundary",
                "name": "Loop subprocess boundary",
                "summary": "Prevent loop orchestration subprocess boundaries.",
                "rationale": "Exercise error-severity parsing for command rules.",
                "remediation": "Update rule declaration.",
                "scope": "harness/fitness-functions",
                "severity": "error",
                "side_effect_free": True,
                "adapter": "command",
                "command": [
                    "uv",
                    "run",
                    "python",
                    "harness/fitness-functions/check_loop_subprocess_boundary.py",
                ],
            }
        ],
    )

    catalog = build_rule_catalog(tmp_path)
    assert len(catalog) == 1
    definition = catalog[0]

    assert definition.metadata.rule_id == "architecture.loop-subprocess-boundary"
    assert definition.metadata.adapter == RuleAdapter.COMMAND
    assert definition.metadata.severity == RuleSeverity.ERROR
    assert definition.command == (
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_loop_subprocess_boundary.py",
    )


def test_build_rule_catalog_resolves_manifest_config_file_to_absolute_path(
    tmp_path: Path,
) -> None:
    """Resolve config_file entries against the manifest directory."""
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            {
                "rule_id": "architecture.loop-subprocess-boundary",
                "name": "Loop subprocess boundary",
                "summary": "Enforce subprocess allowlist boundaries.",
                "rationale": "Exercise config-file resolution for command rules.",
                "remediation": "Update rule declaration.",
                "scope": "src/engineeringagent",
                "severity": "error",
                "side_effect_free": True,
                "adapter": "command",
                "command": [
                    "uv",
                    "run",
                    "python",
                    "harness/fitness-functions/check_loop_subprocess_boundary.py",
                ],
                "config_file": "policies/loop_subprocess_boundary.yaml",
            }
        ],
    )

    catalog = build_rule_catalog(tmp_path)

    assert len(catalog) == 1
    assert (
        catalog[0].config_file
        == (
            manifest_path.parent / "policies" / "loop_subprocess_boundary.yaml"
        ).resolve()
    )


def test_build_rule_catalog_rejects_config_file_outside_project_root(
    tmp_path: Path,
) -> None:
    """Reject config_file paths that escape the repository root."""
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            {
                "rule_id": "architecture.loop-subprocess-boundary",
                "name": "Loop subprocess boundary",
                "summary": "Enforce subprocess allowlist boundaries.",
                "rationale": "Exercise repository-local config-file policy.",
                "remediation": "Update rule declaration.",
                "scope": "src/engineeringagent",
                "severity": "error",
                "side_effect_free": True,
                "adapter": "command",
                "command": [
                    "uv",
                    "run",
                    "python",
                    "harness/fitness-functions/check_loop_subprocess_boundary.py",
                ],
                "config_file": "../../../outside.yaml",
            }
        ],
    )

    with pytest.raises(ValueError) as excinfo:
        build_rule_catalog(tmp_path)

    assert "config_file must resolve within project root" in str(excinfo.value)
