#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_path() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main() -> int:
    _bootstrap_path()
    from agent_harness.validator import validate

    parser = argparse.ArgumentParser(prog="validate_specs.py")
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    messages = validate(project_root=project_root, schema_only=args.schema_only)
    if messages:
        for msg in messages:
            print(msg)
        return 1
    print("spec validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
