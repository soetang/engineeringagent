from __future__ import annotations

import json
from typing import Any

from engineeringagent.fitness.contracts import CONTRACT_VERSION


def emit_result_envelope(
    *,
    rule_id: str,
    status: str,
    severity: str,
    summary: str,
    violations: list[str],
    details: dict[str, Any] | None = None,
) -> None:
    """Emit a deterministic JSON payload matching FitnessRuleResult.

    This is the supported helper surface for harness fitness functions.
    """

    payload: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "rule_id": rule_id,
        "status": status,
        "severity": severity,
        "summary": summary,
        "violations": violations,
    }
    if details is not None:
        payload["details"] = details

    print(json.dumps(payload, separators=(",", ":")))
