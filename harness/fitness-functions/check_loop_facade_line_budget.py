from __future__ import annotations

import json
from pathlib import Path


RULE_ID = "architecture.loop-facade-line-budget"
BASELINE_LINE_COUNT = 1436
MAX_LINE_BUDGET = 650


def main() -> int:
    loop_path = Path("src/engineeringagent/loop.py")
    lines = len(loop_path.read_text(encoding="utf-8").splitlines())

    violations: list[str] = []
    if lines >= BASELINE_LINE_COUNT:
        violations.append(
            "src/engineeringagent/loop.py line count must stay below "
            f"{BASELINE_LINE_COUNT}; current={lines}"
        )
    if lines > MAX_LINE_BUDGET:
        violations.append(
            "src/engineeringagent/loop.py line count must be <= "
            f"{MAX_LINE_BUDGET}; current={lines}"
        )

    status = "pass" if not violations else "fail"
    summary = (
        f"loop facade line budget satisfied at {lines} lines."
        if status == "pass"
        else f"Detected {len(violations)} loop facade line-budget violation(s)."
    )

    print(
        json.dumps(
            {
                "contract_version": "1.0",
                "rule_id": RULE_ID,
                "status": status,
                "severity": "error",
                "summary": summary,
                "violations": violations,
            },
            separators=(",", ":"),
        )
    )
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
