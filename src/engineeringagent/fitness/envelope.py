from __future__ import annotations

import json
from typing import Any

from engineeringagent.fitness.contracts import CONTRACT_VERSION, FitnessRuleResult


def emit_result_envelope(result: FitnessRuleResult) -> None:
    """Emit a deterministic JSON payload matching FitnessRuleResult.

    This is the supported helper surface for harness fitness functions.
    """

    payload: dict[str, Any] = result.model_dump(mode="json", exclude_none=True)
    payload["contract_version"] = CONTRACT_VERSION
    print(json.dumps(payload, separators=(",", ":")))
