from __future__ import annotations

import pytest
from pydantic import ValidationError

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleMetadata,
    FitnessRuleResult,
)


def test_rule_metadata_requires_side_effect_free_true() -> None:
    """Reject rule metadata that does not declare side-effect-free execution."""
    with pytest.raises(ValidationError):
        FitnessRuleMetadata.model_validate(
            {
                "rule_id": "architecture.dep-direction",
                "name": "Dependency directionality",
                "summary": "Prevent invalid dependency imports across boundaries.",
                "rationale": "Preserves module boundaries and reviewability.",
                "remediation": "Refactor imports to approved dependency direction.",
                "scope": "src/engineeringagent",
                "severity": "error",
                "adapter": "python",
                "source": "builtin",
                "side_effect_free": False,
            }
        )


def test_rule_result_requires_versioned_result_envelope() -> None:
    """Accept result payloads that include the explicit contract version."""
    result = FitnessRuleResult.model_validate(
        {
            "contract_version": CONTRACT_VERSION,
            "rule_id": "architecture.dep-direction",
            "status": "pass",
            "severity": "error",
            "summary": "Boundary contract is satisfied.",
            "violations": [],
        }
    )

    assert result.contract_version == CONTRACT_VERSION


def test_rule_result_rejects_missing_contract_version() -> None:
    """Reject result payloads that omit the required contract version."""
    with pytest.raises(ValidationError):
        FitnessRuleResult.model_validate(
            {
                "rule_id": "architecture.dep-direction",
                "status": "pass",
                "severity": "error",
                "summary": "Boundary contract is satisfied.",
            }
        )
