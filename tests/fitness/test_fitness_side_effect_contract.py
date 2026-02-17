from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import execute_rule_definition
from engineeringagent.checks import (
    FitnessRuleMetadata,
    RuleAdapter,
    RuleSeverity,
)
from engineeringagent.checks import FitnessRuleDefinition


def test_execute_rule_definition_rejects_non_side_effect_free_rules(
    tmp_path: Path,
) -> None:
    """Reject execution when a rule does not declare side-effect-free behavior."""
    metadata = FitnessRuleMetadata.model_construct(
        rule_id="custom.side-effect",
        name="Invalid side effect declaration",
        summary="Rule metadata should require side_effect_free=true.",
        rationale="Fitness rules must remain safe for parallel execution.",
        remediation="Update the rule contract declaration to true.",
        scope="harness/fitness-functions/rules.yaml",
        severity=RuleSeverity.WARNING,
        adapter=RuleAdapter.COMMAND,
        source="custom",
        side_effect_free=False,
    )
    definition = FitnessRuleDefinition(
        metadata=metadata,
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=("python", "-c", "print('ignored')"),
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == "error"
    assert result.rule_id == "custom.side-effect"
    assert "side_effect_free" in result.summary
