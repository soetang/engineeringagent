from __future__ import annotations

import pytest

from engineeringagent import checks
from engineeringagent.checks import (
    ChecksRunResult,
    emit_fitness_result,
    emit_result_envelope,
    load_harness_checks_document,
    render_fitness_catalog,
    run_checks,
)
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


def test_checks_supported_exports_are_importable() -> None:
    assert callable(run_checks)
    assert callable(emit_fitness_result)
    assert emit_result_envelope is emit_fitness_result
    assert callable(load_harness_checks_document)
    assert callable(render_fitness_catalog)
    assert ChecksRunResult is not None
    assert set(checks.__all__) == {
        "ChecksRunResult",
        "emit_fitness_result",
        "emit_result_envelope",
        "load_harness_checks_document",
        "render_fitness_catalog",
        "run_checks",
    }


def test_checks_emit_fitness_result_is_deterministic_and_validates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    emit_fitness_result(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id="architecture.dep-direction",
            status=RuleStatus.PASS,
            severity=RuleSeverity.ERROR,
            summary="Boundary contract is satisfied.",
            violations=[],
        )
    )

    stdout = capsys.readouterr().out
    expected = (
        '{"contract_version":"1.0",'
        '"rule_id":"architecture.dep-direction",'
        '"status":"pass",'
        '"severity":"error",'
        '"summary":"Boundary contract is satisfied.",'
        '"violations":[]}\n'
    )
    assert stdout == expected
