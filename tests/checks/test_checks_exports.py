from __future__ import annotations

import pytest

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


def test_checks_supported_exports_are_importable() -> None:
    from engineeringagent.checks import (
        emit_fitness_result,
        emit_result_envelope,
        run_checks,
    )

    assert callable(run_checks)
    assert callable(emit_fitness_result)
    assert emit_result_envelope is emit_fitness_result


def test_checks_emit_fitness_result_is_deterministic_and_validates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from engineeringagent.checks import emit_fitness_result

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
