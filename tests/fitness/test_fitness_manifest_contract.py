from __future__ import annotations

import pytest
from pydantic import ValidationError

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
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


def test_custom_manifest_rejects_builtin_rule_references() -> None:
    """Reject builtin-rule references in declaration-driven command manifests."""
    with pytest.raises(ValidationError) as excinfo:
        CustomRuleManifest.model_validate(
            {
                "contract_version": CONTRACT_VERSION,
                "rules": [
                    {"builtin": "architecture.dep-directionality"},
                    {"builtin": "architecture.loop-subprocess-boundary"},
                ],
            }
        )

    assert "builtin manifest references are no longer supported" in str(excinfo.value)
