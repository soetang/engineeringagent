from __future__ import annotations

import json


CONTRACT_VERSION = "1.0"


def emit_result_envelope(
    *,
    rule_id: str,
    status: str,
    severity: str,
    summary: str,
    violations: list[str],
) -> None:
    print(
        json.dumps(
            {
                "contract_version": CONTRACT_VERSION,
                "rule_id": rule_id,
                "status": status,
                "severity": severity,
                "summary": summary,
                "violations": violations,
            },
            separators=(",", ":"),
        )
    )
