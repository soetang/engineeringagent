from __future__ import annotations

import pytest

from engineeringagent import checks
from engineeringagent.checks import (
    ChecksRunResult,
    emit_fitness_result,
    emit_result_envelope,
    list_check_groups,
    load_harness_checks_document,
    normalize_groups,
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
    assert callable(list_check_groups)
    assert callable(load_harness_checks_document)
    assert callable(normalize_groups)
    assert callable(render_fitness_catalog)
    assert ChecksRunResult is not None
    assert set(checks.__all__) == {
        "ChecksRunResult",
        "emit_fitness_result",
        "emit_result_envelope",
        "list_check_groups",
        "load_harness_checks_document",
        "normalize_groups",
        "render_fitness_catalog",
        "run_checks",
    }


def test_checks_group_helpers_use_deterministic_contract() -> None:
    assert list_check_groups() == ("validate", "commands", "fitness", "reviewers")
    assert normalize_groups(["fitness", "commands", "fitness"]) == (
        "commands",
        "fitness",
    )


@pytest.mark.parametrize(
    "legacy_name",
    [
        "load_reviewer_config",
        "parse_reviewer_decision",
        "plan_reviewers",
        "run_planned_command_checks",
        "run_planned_fitness_checks",
        "run_planned_reviewer_checks",
    ],
)
def test_checks_does_not_export_removed_legacy_runtime_helpers(legacy_name: str) -> None:
    assert legacy_name not in checks.__all__
    assert not hasattr(checks, legacy_name)


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
