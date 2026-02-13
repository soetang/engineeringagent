from __future__ import annotations

from pathlib import Path

import yaml

from engineeringagent.fitness.contracts import CONTRACT_VERSION, RuleSource
from engineeringagent.fitness.registry import (
    DEFAULT_CUSTOM_RULE_MANIFEST,
    load_custom_rule_definitions,
)


def _write_manifest(path: Path, rule_id: str = "custom.docs-links") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "contract_version": CONTRACT_VERSION,
                "rules": [
                    {
                        "rule_id": rule_id,
                        "name": "Docs links check",
                        "summary": "Validate markdown links resolve.",
                        "rationale": "Broken links hide docs regressions.",
                        "remediation": "Update stale links.",
                        "scope": "docs",
                        "severity": "warning",
                        "side_effect_free": True,
                        "adapter": "command",
                        "command": ["uv", "run", "python", "scripts/check_docs.py"],
                    }
                ],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def test_load_custom_rule_definitions_returns_empty_when_default_missing(
    tmp_path: Path,
) -> None:
    """Return no custom definitions when manifest does not exist."""
    definitions = load_custom_rule_definitions(tmp_path)

    assert definitions == []


def test_load_custom_rule_definitions_reads_default_manifest_path(
    tmp_path: Path,
) -> None:
    """Load custom definitions from the default repository manifest path."""
    manifest_path = tmp_path / DEFAULT_CUSTOM_RULE_MANIFEST
    _write_manifest(manifest_path)

    definitions = load_custom_rule_definitions(tmp_path)

    assert len(definitions) == 1
    assert definitions[0].metadata.rule_id == "custom.docs-links"
    assert definitions[0].metadata.source == RuleSource.CUSTOM
    assert definitions[0].command == (
        "uv",
        "run",
        "python",
        "scripts/check_docs.py",
    )
