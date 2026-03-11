from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engineeringagent.checks.fitness.contracts import CONTRACT_VERSION
from engineeringagent.checks.fitness.registry import build_rule_catalog


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


def test_duplicate_rule_ids_in_manifest_fail_fast(tmp_path: Path) -> None:
    """Raise actionable errors when command manifest IDs collide."""
    manifest_path = tmp_path / "harness" / "fitness_functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            {
                "rule_id": "architecture.dep-direction",
                "name": "Directionality A",
                "summary": "First collision test rule.",
                "rationale": "Exercise duplicate detection.",
                "remediation": "Rename manifest rule IDs.",
                "scope": "docs",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "command": ["python", "scripts/custom_rule.py"],
            },
            {
                "rule_id": "architecture.dep-direction",
                "name": "Directionality B",
                "summary": "Second collision test rule.",
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
        build_rule_catalog(tmp_path)

    message = str(excinfo.value)
    assert "duplicate fitness rule_id detected" in message
    assert "architecture.dep-direction" in message
    assert "rules[0]" in message
    assert "rules[1]" in message


def test_duplicate_rule_ids_within_custom_manifest_fail_fast(tmp_path: Path) -> None:
    """Raise actionable errors when custom manifest IDs collide."""
    manifest_path = tmp_path / "harness" / "fitness_functions" / "rules.yaml"
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
        build_rule_catalog(tmp_path)

    message = str(excinfo.value)
    assert "duplicate fitness rule_id detected" in message
    assert "custom.docs-links" in message
    assert "rules[0]" in message
    assert "rules[1]" in message
