from __future__ import annotations

from pathlib import Path
import sys

import yaml

from engineeringagent.fitness.contracts import CONTRACT_VERSION
from engineeringagent.fitness.runner import run_rule_catalog


def _command_rule(
    rule_id: str,
    *,
    sleep_seconds: float,
    status: str,
) -> dict[str, object]:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "rule_id": rule_id,
        "status": status,
        "severity": "error",
        "summary": f"{rule_id} completed",
        "violations": [] if status == "pass" else [f"{rule_id} violation"],
    }
    runner = (
        f"import json,time;time.sleep({sleep_seconds});print(json.dumps({payload!r}))"
    )
    return {
        "rule_id": rule_id,
        "name": f"Rule {rule_id}",
        "summary": "Rule for parallel runner tests.",
        "rationale": "Runner output should stay deterministic.",
        "remediation": "Fix test fixtures.",
        "scope": "tests",
        "severity": "error",
        "side_effect_free": True,
        "adapter": "command",
        "command": [sys.executable, "-c", runner],
    }


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


def test_run_rule_catalog_parallel_output_is_sorted_by_rule_id(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            _command_rule("z.rule", sleep_seconds=0.01, status="pass"),
            _command_rule("a.rule", sleep_seconds=0.03, status="pass"),
            _command_rule("m.rule", sleep_seconds=0.02, status="pass"),
        ],
    )

    summary = run_rule_catalog(
        tmp_path,
        jobs=3,
        manifest_path=manifest_path,
    )

    assert [result.rule_id for result in summary.results] == [
        "a.rule",
        "m.rule",
        "z.rule",
    ]
    assert summary.has_failures is False


def test_run_rule_catalog_returns_failure_when_rule_fails(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    _write_manifest(
        manifest_path,
        [
            _command_rule("a.pass", sleep_seconds=0.0, status="pass"),
            _command_rule("b.fail", sleep_seconds=0.0, status="fail"),
        ],
    )

    summary = run_rule_catalog(
        tmp_path,
        jobs=2,
        manifest_path=manifest_path,
    )

    assert summary.has_failures is True
