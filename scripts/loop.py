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
    from engineeringagent.loop import run_loop

    parser = argparse.ArgumentParser(prog="loop.py")
    parser.add_argument("feature_paths", nargs="+")
    parser.add_argument("--gate-profile", default="loop_fast")
    parser.add_argument("--implement-command")
    parser.add_argument("--opencode-prompt")
    parser.add_argument("--skip-implement", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=50)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    return run_loop(
        project_root=project_root,
        feature_paths=args.feature_paths,
        gate_profile=args.gate_profile,
        implement_command=args.implement_command,
        opencode_prompt=args.opencode_prompt,
        skip_implement=args.skip_implement,
        dry_run=args.dry_run,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    raise SystemExit(main())
