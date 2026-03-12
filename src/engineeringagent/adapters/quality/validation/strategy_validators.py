from __future__ import annotations

from engineeringagent.adapters.quality.validation.contracts import StrategyValidator
from engineeringagent.adapters.quality.validation.fitness_catalog_validator import (
    FitnessCatalogStrategyValidator,
)
from engineeringagent.adapters.quality.validation.reviewer_prompt_validator import (
    ReviewerPromptStrategyValidator,
)

_DEFAULT_STRATEGY_VALIDATORS: tuple[StrategyValidator, ...] = (
    ReviewerPromptStrategyValidator(),
    FitnessCatalogStrategyValidator(),
)


def default_strategy_validators() -> tuple[StrategyValidator, ...]:
    """Return default strategy-owned validators for validate composition."""

    # ValidationRegistry is the canonical deterministic ordering boundary.
    return _DEFAULT_STRATEGY_VALIDATORS
