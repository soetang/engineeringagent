#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType


def _load_commit_messages_module() -> ModuleType:
    """Load sibling commit_messages.py via file path.

    This script lives in a non-package directory (harness/fitness_functions), so
    importing by module name is not reliable under all tooling (e.g. pylint).
    """

    module_path = Path(__file__).resolve().parent / "commit_messages.py"
    spec = importlib.util.spec_from_file_location("commit_messages", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load commit_messages from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_commit_messages = _load_commit_messages_module()
commit_subjects_from_range = _commit_messages.commit_subjects_from_range
subject_from_commit_message_file = _commit_messages.subject_from_commit_message_file
validate_commit_subject = _commit_messages.validate_commit_subject
validate_commit_subjects = _commit_messages.validate_commit_subjects


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for commit-subject policy validation."""
    parser = argparse.ArgumentParser(
        description="Validate commit subjects against `type: summary` policy."
    )
    parser.add_argument(
        "--project-root",
        default=Path(__file__).resolve().parents[2],
        type=Path,
        help="repository root for git commit-range validation",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--commit-msg-file",
        type=Path,
        help="path to COMMIT_EDITMSG file (commit-msg hook mode)",
    )
    mode.add_argument(
        "--commit-range",
        help="git commit range to validate (CI mode, e.g. origin/main..HEAD)",
    )
    return parser


def _run_commit_msg_file_mode(commit_msg_file: Path) -> int:
    try:
        subject = subject_from_commit_message_file(commit_msg_file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"commit message validation: {exc}")
        return 1

    issue = validate_commit_subject(subject)
    if issue is not None:
        print(f"commit message validation failed: {issue}")
        print(f"subject: {subject}")
        return 1

    print("commit message validation: ok")
    return 0


def _run_commit_range_mode(project_root: Path, commit_range: str) -> int:
    try:
        subjects = commit_subjects_from_range(project_root, commit_range)
    except ValueError as exc:
        print(f"commit range validation failed: {exc}")
        return 1

    issues = validate_commit_subjects(subjects)
    if issues:
        for issue in issues:
            print(issue)
        return 1

    print("commit range validation: ok")
    return 0


def main() -> int:
    """Run commit message validation and exit with a shell-friendly code."""
    parser = build_parser()
    args = parser.parse_args()

    if args.commit_msg_file is not None:
        return _run_commit_msg_file_mode(args.commit_msg_file)

    return _run_commit_range_mode(args.project_root.resolve(), args.commit_range)


if __name__ == "__main__":
    raise SystemExit(main())
