from __future__ import annotations

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.fitness.runtime import plan_fitness_checks
from engineeringagent.domain.quality import HarnessCheckPhase, HarnessChecksDocument


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
