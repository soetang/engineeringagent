from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .gates import list_profiles, load_gate_config, run_profile
from .loop import run_loop
from .validator import validate


def cmd_validate(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    messages = validate(project_root=project_root, schema_only=args.schema_only)
    if messages:
        for msg in messages:
            print(msg)
        return 1
    print("spec validation: ok")
    return 0


def cmd_gates_list(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    config = load_gate_config(project_root / "harness" / "gates.yaml")
    for name in list_profiles(config):
        print(name)
    return 0


def cmd_gates_run(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    config = load_gate_config(project_root / "harness" / "gates.yaml")
    ok, failed = run_profile(config=config, profile=args.profile, cwd=project_root)
    if not ok:
        print(f"gates profile failed: {failed}")
        return 1
    print(f"gates profile passed: {args.profile}")
    return 0


def cmd_loop_run(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    return run_loop(
        project_root=project_root,
        feature_id=args.feature_id,
        gate_profile=args.gate_profile,
        implement_command=args.implement_command,
        opencode_prompt=args.opencode_prompt,
        skip_implement=args.skip_implement,
        dry_run=args.dry_run,
        max_attempts=args.max_attempts,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-harness",
        description="Human-gated CLI harness for feature-driven coding loops.",
    )
    parser.add_argument("--project-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="validate feature specs")
    validate_parser.add_argument("--schema-only", action="store_true")
    validate_parser.set_defaults(func=cmd_validate)

    gates_parser = sub.add_parser("gates", help="run configured gate profiles")
    gates_sub = gates_parser.add_subparsers(dest="gates_cmd", required=True)

    gates_list_parser = gates_sub.add_parser("list", help="list gate profiles")
    gates_list_parser.set_defaults(func=cmd_gates_list)

    gates_run_parser = gates_sub.add_parser("run", help="run a gate profile")
    gates_run_parser.add_argument("--profile", required=True)
    gates_run_parser.set_defaults(func=cmd_gates_run)

    loop_parser = sub.add_parser("loop", help="loop operations")
    loop_sub = loop_parser.add_subparsers(dest="loop_cmd", required=True)

    loop_run_parser = loop_sub.add_parser("run", help="run one loop iteration")
    loop_run_parser.add_argument("--feature-id", help="pin the loop to a specific feature id")
    loop_run_parser.add_argument("--gate-profile", default="loop_fast", help="gate profile name")
    loop_run_parser.add_argument(
        "--implement-command",
        help="custom implementation command; defaults to opencode build-agent run",
    )
    loop_run_parser.add_argument(
        "--opencode-prompt",
        help="override generated opencode prompt when using default implementer",
    )
    loop_run_parser.add_argument(
        "--skip-implement",
        action="store_true",
        help="skip the implementation command and run gates/verification only",
    )
    loop_run_parser.add_argument("--dry-run", action="store_true")
    loop_run_parser.add_argument("--max-attempts", type=int, default=3)
    loop_run_parser.set_defaults(func=cmd_loop_run)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    sys.exit(main())
