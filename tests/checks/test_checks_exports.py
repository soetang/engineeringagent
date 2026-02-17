from __future__ import annotations

import pytest

from engineeringagent.checks import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


def test_checks_supported_exports_are_importable() -> None:
    from engineeringagent.checks import (
        FitnessRuleDefinition,
        RuleStatus,
        emit_fitness_result,
        emit_result_envelope,
        render_rule_catalog_markdown,
        run_checks,
        run_rule_catalog,
        write_rule_catalog_markdown,
    )

    assert callable(run_checks)
    assert callable(emit_fitness_result)
    assert emit_result_envelope is emit_fitness_result
    assert callable(run_rule_catalog)
    assert callable(render_rule_catalog_markdown)
    assert callable(write_rule_catalog_markdown)
    assert FitnessRuleDefinition is not None
    assert RuleStatus is not None


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
