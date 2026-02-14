from __future__ import annotations

import time
from pathlib import Path

import yaml

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleMetadata,
    RuleAdapter,
    RuleSeverity,
    RuleSource,
)
from engineeringagent.fitness.registry import FitnessRuleDefinition
from engineeringagent.fitness.runner import run_rule_catalog


def _python_rule(
    rule_id: str,
    *,
    sleep_seconds: float,
    status: str,
) -> FitnessRuleDefinition:
    def _runner(_project_root: Path) -> dict[str, object]:
        time.sleep(sleep_seconds)
        return {
            "contract_version": CONTRACT_VERSION,
            "rule_id": rule_id,
            "status": status,
            "severity": "error",
            "summary": f"{rule_id} completed",
            "violations": [] if status == "pass" else [f"{rule_id} violation"],
        }

    return FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id=rule_id,
            name=f"Rule {rule_id}",
            summary="Rule for parallel runner tests.",
            rationale="Runner output should stay deterministic.",
            remediation="Fix test fixtures.",
            scope="tests",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.PYTHON,
            source=RuleSource.BUILTIN,
            side_effect_free=True,
        ),
        origin=f"builtin:{rule_id}",
        python_callable=_runner,
    )


def _write_builtin_manifest(path: Path, rule_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "contract_version": CONTRACT_VERSION,
                "rules": [{"builtin": rule_id} for rule_id in rule_ids],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def test_run_rule_catalog_parallel_output_is_sorted_by_rule_id(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_builtin_manifest(manifest_path, ["z.rule", "a.rule", "m.rule"])

    summary = run_rule_catalog(
        tmp_path,
        jobs=3,
        manifest_path=manifest_path,
        builtin_rules=[
            _python_rule("z.rule", sleep_seconds=0.01, status="pass"),
            _python_rule("a.rule", sleep_seconds=0.03, status="pass"),
            _python_rule("m.rule", sleep_seconds=0.02, status="pass"),
        ],
    )

    assert [result.rule_id for result in summary.results] == [
        "a.rule",
        "m.rule",
        "z.rule",
    ]
    assert summary.has_failures is False


def test_run_rule_catalog_returns_failure_when_rule_fails(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_builtin_manifest(manifest_path, ["a.pass", "b.fail"])

    summary = run_rule_catalog(
        tmp_path,
        jobs=2,
        manifest_path=manifest_path,
        builtin_rules=[
            _python_rule("a.pass", sleep_seconds=0.0, status="pass"),
            _python_rule("b.fail", sleep_seconds=0.0, status="fail"),
        ],
    )

    assert summary.has_failures is True
