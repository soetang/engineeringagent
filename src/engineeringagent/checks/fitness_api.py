from __future__ import annotations

import json
from typing import Any

from engineeringagent.fitness.contracts import CONTRACT_VERSION, FitnessRuleResult


def emit_fitness_result(result: FitnessRuleResult) -> None:
    """Emit a deterministic JSON fitness result envelope.

    The canonical implementation is introduced during the FEAT-097 migration.
    """

    payload: dict[str, Any] = result.model_dump(mode="json", exclude_none=True)
    payload["contract_version"] = CONTRACT_VERSION
    print(json.dumps(payload, separators=(",", ":")))
