from __future__ import annotations

from engineeringagent.checks.fitness_api import emit_fitness_result
from engineeringagent.fitness.contracts import FitnessRuleResult


def emit_result_envelope(result: FitnessRuleResult) -> None:
    """Emit a deterministic JSON payload matching FitnessRuleResult.

    This is the supported helper surface for harness fitness functions.
    """

    emit_fitness_result(result)
