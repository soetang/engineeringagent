#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


ALLOWED_COMMIT_TYPES: tuple[str, ...] = (
    "feat",
    "fix",
    "spec",
    "docs",
    "chore",
    "test",
)

_ALLOWED_TYPES_PATTERN = "|".join(re.escape(t) for t in ALLOWED_COMMIT_TYPES)
COMMIT_SUBJECT_PATTERN = re.compile(rf"^({_ALLOWED_TYPES_PATTERN}): [^\n]+$")


def validate_commit_subject(subject: str) -> str | None:
    """Validate one commit subject against `type: summary` policy."""
    if "\n" in subject:
        return "subject must be a single line"

    if COMMIT_SUBJECT_PATTERN.fullmatch(subject):
        return None

    allowed = ", ".join(ALLOWED_COMMIT_TYPES)
    return f"subject must match `type: summary` with allowed types [{allowed}]"


def subject_from_commit_message_file(commit_message_file: Path) -> str:
    """Extract the commit subject from a commit message file."""
    for line in commit_message_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped
    raise ValueError("commit message file does not contain a subject line")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for commit-subject policy validation."""
    parser = argparse.ArgumentParser(
        description="Validate a commit message subject against `type: summary` policy."
    )
    parser.add_argument(
        "--commit-msg-file",
        required=True,
        type=Path,
        help="path to COMMIT_EDITMSG file (commit-msg hook mode)",
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


def main() -> int:
    """CLI entrypoint for commit subject validation."""
    args = build_parser().parse_args()
    return _run_commit_msg_file_mode(args.commit_msg_file)


if __name__ == "__main__":
    raise SystemExit(main())
