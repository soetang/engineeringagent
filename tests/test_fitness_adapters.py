from __future__ import annotations

from pathlib import Path
import sys

from engineeringagent.fitness.adapters import execute_rule_definition
from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleMetadata,
    RuleAdapter,
    RuleSeverity,
    RuleSource,
    RuleStatus,
)
from engineeringagent.fitness.registry import FitnessRuleDefinition


def _command_definition(command: tuple[str, ...]) -> FitnessRuleDefinition:
    return FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="custom.adapter-pass",
            name="Custom adapter pass",
            summary="Validate command adapter result parsing.",
            rationale="Custom rules need a stable execution contract.",
            remediation="Fix the external rule command output envelope.",
            scope="harness/fitness-functions/rules.yaml",
            severity=RuleSeverity.WARNING,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=command,
    )


def test_execute_rule_definition_runs_command_adapter_with_json_envelope(
    tmp_path: Path,
) -> None:
    """Return validated command-adapter result payloads."""
    rule_script = tmp_path / "rule.py"
    rule_script.write_text(
        "\n".join(
            [
                "import json",
                "print(json.dumps({",
                f"    'contract_version': '{CONTRACT_VERSION}',",
                "    'rule_id': 'custom.adapter-pass',",
                "    'status': 'pass',",
                "    'severity': 'warning',",
                "    'summary': 'All checks passed.',",
                "    'violations': [],",
                "}))",
            ]
        ),
        encoding="utf-8",
    )

    result = execute_rule_definition(
        _command_definition((sys.executable, str(rule_script))),
        project_root=tmp_path,
    )

    assert result.status == RuleStatus.PASS
    assert result.rule_id == "custom.adapter-pass"


def test_execute_rule_definition_runs_python_adapter_callable(tmp_path: Path) -> None:
    """Execute built-in Python adapter callables through a shared runner."""

    def _rule_callable(project_root: Path) -> dict[str, object]:
        assert project_root == tmp_path
        return {
            "contract_version": CONTRACT_VERSION,
            "rule_id": "builtin.python-adapter",
            "status": "pass",
            "severity": "error",
            "summary": "Built-in Python adapter ran.",
            "violations": [],
        }

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="builtin.python-adapter",
            name="Built-in python adapter",
            summary="Validate Python adapter dispatch.",
            rationale="Built-in rules run natively in Python.",
            remediation="Provide a valid Python fitness callable.",
            scope="src/engineeringagent",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.PYTHON,
            source=RuleSource.BUILTIN,
            side_effect_free=True,
        ),
        origin="builtin:builtin.python-adapter",
        python_callable=_rule_callable,
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.PASS
    assert result.rule_id == "builtin.python-adapter"
