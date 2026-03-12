from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engineeringagent.checks.fitness import validator as fitness_validator
from engineeringagent.checks.fitness.validator import FitnessCatalogStrategyValidator
from engineeringagent.adapters.quality.validation.contracts import ValidationContext


def _context(project_root: Path) -> ValidationContext:
    return ValidationContext(
        project_root=project_root,
        docs_root=project_root / "docs",
        schema_only=False,
    )


def test_fitness_strategy_validator_reports_manifest_contract_errors(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "harness" / "fitness_functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [{"builtin": "legacy.rule"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    issues = FitnessCatalogStrategyValidator().validate(context=_context(tmp_path))

    assert len(issues) == 1
    assert issues[0].scope == "strategy"
    assert issues[0].validator_id == "fitness.catalog"
    assert issues[0].path == "harness/fitness_functions/rules.yaml"
    assert "builtin manifest references are no longer supported" in issues[0].message


def test_fitness_strategy_validator_returns_no_issues_for_valid_manifest(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "harness" / "fitness_functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [
                    {
                        "rule_id": "custom.docs-links",
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
        ),
        encoding="utf-8",
    )

    issues = FitnessCatalogStrategyValidator().validate(context=_context(tmp_path))

    assert issues == ()


def test_fitness_strategy_validator_reports_manifest_read_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_read_failure(_project_root: Path) -> list[object]:
        raise OSError("permission denied")

    monkeypatch.setattr(fitness_validator, "build_rule_catalog", _raise_read_failure)

    issues = FitnessCatalogStrategyValidator().validate(context=_context(tmp_path))

    assert len(issues) == 1
    assert issues[0].scope == "strategy"
    assert issues[0].validator_id == "fitness.catalog"
    assert issues[0].path == "harness/fitness_functions/rules.yaml"
    assert issues[0].code == "fitness.catalog.read-failure"
    assert "failed to read fitness manifest" in issues[0].message
