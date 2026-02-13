from __future__ import annotations

import re
import subprocess
from pathlib import Path


ALLOWED_COMMIT_TYPES: tuple[str, ...] = (
    "feat",
    "fix",
    "spec",
    "docs",
    "chore",
    "test",
)
COMMIT_SUBJECT_PATTERN = re.compile(r"^(feat|fix|spec|docs|chore|test): [^\n]+$")


def validate_commit_subject(subject: str) -> str | None:
    """Validate one commit subject against repository policy.

    Args:
        subject: Single commit subject line.

    Returns:
        Error message when invalid; otherwise None.
    """
    if "\n" in subject:
        return "subject must be a single line"

    if COMMIT_SUBJECT_PATTERN.fullmatch(subject):
        return None

    allowed = ", ".join(ALLOWED_COMMIT_TYPES)
    return f"subject must match `type: summary` with allowed types [{allowed}]"


def subject_from_commit_message_file(commit_message_file: Path) -> str:
    """Extract the commit subject from a commit message file.

    Args:
        commit_message_file: Path passed by git commit-msg hook.

    Returns:
        First non-empty, non-comment line.

    Raises:
        ValueError: If no commit subject line is present.
    """
    for line in commit_message_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped
    raise ValueError("commit message file does not contain a subject line")


def validate_commit_subjects(subjects: list[str]) -> list[str]:
    """Validate many commit subjects and return deterministic errors.

    Args:
        subjects: Commit subject lines to validate.

    Returns:
        Sorted validation errors with positional context.
    """
    errors: list[str] = []
    for index, subject in enumerate(subjects, start=1):
        issue = validate_commit_subject(subject)
        if issue is not None:
            errors.append(f"commit[{index}] `{subject}`: {issue}")
    return errors


def commit_subjects_from_range(project_root: Path, commit_range: str) -> list[str]:
    """Read commit subjects from a git revision range.

    Args:
        project_root: Repository root to run git in.
        commit_range: Git revision range, e.g. ``origin/main..HEAD``.

    Returns:
        Commit subjects in git log order for the range.

    Raises:
        ValueError: If git log fails for the provided range.
    """
    proc = subprocess.run(
        ["git", "log", "--format=%s", commit_range],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        message = output or f"git log failed for range: {commit_range}"
        raise ValueError(message)

    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return lines
