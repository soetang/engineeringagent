#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_path() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main() -> int:
    _bootstrap_path()
    from agent_harness.opencode_permissions import run_permission_probe

    project_root = Path(__file__).resolve().parents[1]
    result = run_permission_probe(project_root)

    if result.output:
        print(result.output, end="" if result.output.endswith("\n") else "\n")

    if result.ok:
        print("permission probe: ok")
        return 0

    print(f"permission probe: failed ({result.reason})")
    print("hint: ensure .opencode/agents/build.md and opencode.json both set build permissions to allow-all")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
