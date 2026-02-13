from __future__ import annotations

import pytest
from pydantic import ValidationError

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    BuiltinRuleManifestReference,
    CustomRuleManifest,
    CustomRuleManifestEntry,
)


def test_custom_manifest_accepts_versioned_command_rules() -> None:
    """Accept manifest entries that match the versioned command contract."""
    manifest = CustomRuleManifest.model_validate(
        {
            "contract_version": CONTRACT_VERSION,
            "rules": [
                {
                    "rule_id": "custom.docs-links",
                    "name": "Docs links check",
                    "summary": "Validate all markdown links resolve.",
                    "rationale": "Broken links reduce docs reliability.",
                    "remediation": "Update or remove stale links.",
                    "scope": "docs",
                    "severity": "warning",
                    "side_effect_free": True,
                    "adapter": "command",
                    "command": ["uv", "run", "python", "scripts/check_docs_links.py"],
                    "timeout_seconds": 30,
                }
            ],
        }
    )

    assert manifest.contract_version == CONTRACT_VERSION
    assert isinstance(manifest.rules[0], CustomRuleManifestEntry)
    assert manifest.rules[0].adapter == "command"


def test_custom_manifest_rejects_non_command_adapter() -> None:
    """Reject custom manifest entries that use non-command adapters."""
    with pytest.raises(ValidationError):
        CustomRuleManifest.model_validate(
            {
                "contract_version": CONTRACT_VERSION,
                "rules": [
                    {
                        "rule_id": "custom.docs-links",
                        "name": "Docs links check",
                        "summary": "Validate all markdown links resolve.",
                        "rationale": "Broken links reduce docs reliability.",
                        "remediation": "Update or remove stale links.",
                        "scope": "docs",
                        "severity": "warning",
                        "side_effect_free": True,
                        "adapter": "python",
                        "command": [
                            "uv",
                            "run",
                            "python",
                            "scripts/check_docs_links.py",
                        ],
                    }
                ],
            }
        )


def test_custom_manifest_rejects_extra_fields() -> None:
    """Reject custom manifest entries with fields outside the contract."""
    with pytest.raises(ValidationError):
        CustomRuleManifest.model_validate(
            {
                "contract_version": CONTRACT_VERSION,
                "rules": [
                    {
                        "rule_id": "custom.docs-links",
                        "name": "Docs links check",
                        "summary": "Validate all markdown links resolve.",
                        "rationale": "Broken links reduce docs reliability.",
                        "remediation": "Update or remove stale links.",
                        "scope": "docs",
                        "severity": "warning",
                        "side_effect_free": True,
                        "adapter": "command",
                        "command": [
                            "uv",
                            "run",
                            "python",
                            "scripts/check_docs_links.py",
                        ],
                        "unknown": "value",
                    }
                ],
            }
        )


def test_custom_manifest_accepts_builtin_rule_references() -> None:
    """Accept builtin-rule references without metadata duplication blocks."""
    manifest = CustomRuleManifest.model_validate(
        {
            "contract_version": CONTRACT_VERSION,
            "rules": [
                {"builtin": "architecture.dep-directionality"},
                {"builtin": "architecture.loop-subprocess-boundary"},
            ],
        }
    )

    builtin_entries = [
        entry
        for entry in manifest.rules
        if isinstance(entry, BuiltinRuleManifestReference)
    ]

    assert [entry.builtin for entry in builtin_entries] == [
        "architecture.dep-directionality",
        "architecture.loop-subprocess-boundary",
    ]


def test_custom_manifest_accepts_mixed_builtin_and_command_entries() -> None:
    """Allow manifests to mix builtin references and command-backed rules."""
    manifest = CustomRuleManifest.model_validate(
        {
            "contract_version": CONTRACT_VERSION,
            "rules": [
                {"builtin": "architecture.dep-directionality"},
                {
                    "rule_id": "custom.docs-links",
                    "name": "Docs links check",
                    "summary": "Validate all markdown links resolve.",
                    "rationale": "Broken links reduce docs reliability.",
                    "remediation": "Update or remove stale links.",
                    "scope": "docs",
                    "severity": "warning",
                    "side_effect_free": True,
                    "adapter": "command",
                    "command": ["uv", "run", "python", "scripts/check_docs_links.py"],
                },
            ],
        }
    )

    assert isinstance(manifest.rules[0], BuiltinRuleManifestReference)
    assert manifest.rules[0].builtin == "architecture.dep-directionality"
    assert isinstance(manifest.rules[1], CustomRuleManifestEntry)
    assert manifest.rules[1].rule_id == "custom.docs-links"
