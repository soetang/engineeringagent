from __future__ import annotations

from engineeringagent.adapters.quality.validation.strategy_validators import (
    default_strategy_validators,
)


def test_default_strategy_validators_return_stable_registration_order() -> None:
    """Default strategy validators expose stable registration order."""

    validators = default_strategy_validators()

    assert tuple(
        (validator.strategy_type, validator.validator_id) for validator in validators
    ) == (
        ("reviewer", "reviewer.prompt-policy"),
        ("fitness", "fitness.catalog"),
    )
