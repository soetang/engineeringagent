from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.fitness.contracts import RuleStatus
from engineeringagent.checks.fitness.runtime import (
    RunPlannedFitnessChecksRequest,
    plan_fitness_checks,
    run_planned_fitness_checks,
)
from engineeringagent.specs import HarnessCheckPhase, HarnessChecksDocument


def _doc(payload: dict[str, object]) -> HarnessChecksDocument:
    return HarnessChecksDocument.model_validate(payload)


def test_plan_fitness_checks_respects_on_change_and_manual_phase() -> None:
    doc = _doc(
        {
            "contract_version": "1.0",
            "checks": {
                "always": {
                    "type": "fitness",
                    "scope": "all",
                },
                "on_change": {
                    "type": "fitness",
                    "scope": "all",
                    "when": {"on_change": ["src/**"]},
                },
                "manual": {
                    "type": "fitness",
                    "scope": "all",
                    "when": {"phase": "manual"},
                },
            },
        }
    )

    planned = plan_fitness_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(
            paths=("src/app.py",), run_all=False, reason=None
        ),
    )
    by_id = {entry.check_id: entry for entry in planned}
    assert by_id["always"].decision == "run"
    assert by_id["on_change"].decision == "run"

    planned_manual = plan_fitness_checks(
        doc,
        phase=HarnessCheckPhase.MANUAL,
        changed_paths=ChangedPathsResult(
            paths=("src/app.py",), run_all=False, reason=None
        ),
    )
    assert [entry.check_id for entry in planned_manual] == ["manual"]
    assert planned_manual[0].decision == "skip"
    assert planned_manual[0].reason == "manual"


def test_run_planned_fitness_checks_runs_all_rules_before_failing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = _doc(
        {
            "contract_version": "1.0",
            "checks": {
                "fitness_selected": {
                    "type": "fitness",
                    "rule_ids": ["rule_a", "rule_b"],
                }
            },
        }
    )

    definitions = [
        SimpleNamespace(
            metadata=SimpleNamespace(rule_id="rule_a", remediation="fix a")
        ),
        SimpleNamespace(
            metadata=SimpleNamespace(rule_id="rule_b", remediation="fix b")
        ),
    ]
    monkeypatch.setattr(
        "engineeringagent.checks.fitness.runtime.build_rule_catalog",
        lambda _root: list(definitions),
        raising=True,
    )

    called: list[str] = []

    def _execute(definition: object, _root: Path) -> object:
        rule_id = getattr(getattr(definition, "metadata"), "rule_id")
        called.append(rule_id)
        if rule_id == "rule_a":
            return SimpleNamespace(
                rule_id=rule_id,
                status=RuleStatus.FAIL,
                summary="no",
                violations=["violation"],
                details=None,
            )
        return SimpleNamespace(
            rule_id=rule_id,
            status=RuleStatus.PASS,
            summary="ok",
            violations=[],
            details=None,
        )

    monkeypatch.setattr(
        "engineeringagent.checks.fitness.runtime.execute_rule_definition",
        _execute,
        raising=True,
    )

    ok, failed, output, failed_payload = run_planned_fitness_checks(
        RunPlannedFitnessChecksRequest(
            project_root=tmp_path,
            doc=doc,
            phase=HarnessCheckPhase.ITERATION_END,
            changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
        )
    )
    assert called == ["rule_a", "rule_b"]
    assert not ok
    assert failed == "fitness_selected"
    assert "[fitness:rule_a] status=fail" in output
    assert "[fitness:rule_b] status=pass" in output
    assert isinstance(failed_payload, dict)
    assert failed_payload.get("kind") == "fitness_failure"


def test_run_planned_fitness_checks_fails_on_missing_rule_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = _doc(
        {
            "contract_version": "1.0",
            "checks": {
                "fitness_selected": {
                    "type": "fitness",
                    "rule_ids": ["rule_a", "rule_missing"],
                }
            },
        }
    )

    definitions = [
        SimpleNamespace(
            metadata=SimpleNamespace(rule_id="rule_a", remediation="fix a")
        ),
    ]
    monkeypatch.setattr(
        "engineeringagent.checks.fitness.runtime.build_rule_catalog",
        lambda _root: list(definitions),
        raising=True,
    )

    ok, failed, output, failed_payload = run_planned_fitness_checks(
        RunPlannedFitnessChecksRequest(
            project_root=tmp_path,
            doc=doc,
            phase=HarnessCheckPhase.ITERATION_END,
            changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
        )
    )
    assert not ok
    assert failed == "fitness_selected"
    assert "missing_rule_ids=['rule_missing']" in output
    assert isinstance(failed_payload, dict)
    assert failed_payload.get("kind") == "selection_error"
