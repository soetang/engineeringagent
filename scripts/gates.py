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
    from agent_harness.gates import list_profiles, load_gate_config, run_profile

    parser = argparse.ArgumentParser(prog="gates.py")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--profile", required=True)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    config = load_gate_config(project_root / "harness" / "gates.yaml")

    if args.command == "list":
        for name in list_profiles(config):
            print(name)
        return 0

    ok, failed = run_profile(config=config, profile=args.profile, cwd=project_root)
    if not ok:
        print(f"gates profile failed: {failed}")
        return 1
    print(f"gates profile passed: {args.profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
