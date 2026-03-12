from __future__ import annotations

from engineeringagent.checks.fitness.validator import FitnessCatalogStrategyValidator
from engineeringagent.checks.reviewers.validator import ReviewerPromptStrategyValidator
from engineeringagent.adapters.quality.validation.contracts import StrategyValidator

_DEFAULT_STRATEGY_VALIDATORS: tuple[StrategyValidator, ...] = (
    ReviewerPromptStrategyValidator(),
    FitnessCatalogStrategyValidator(),
)


def default_strategy_validators() -> tuple[StrategyValidator, ...]:
    """Return default strategy-owned validators for validate composition."""

    # ValidationRegistry is the canonical deterministic ordering boundary.
    return _DEFAULT_STRATEGY_VALIDATORS
