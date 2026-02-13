from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from engineeringagent.commit_messages import (
    commit_subjects_from_range,
    subject_from_commit_message_file,
    validate_commit_subject,
    validate_commit_subjects,
)


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def test_validate_commit_subject_accepts_allowed_format() -> None:
    assert validate_commit_subject("feat: add deterministic selection") is None
    assert validate_commit_subject("fix: prevent flaky loop retries") is None
    assert validate_commit_subject("spec: enforce metadata contract") is None


def test_validate_commit_subject_rejects_invalid_prefix() -> None:
    issue = validate_commit_subject("refactor: improve readability")
    assert issue is not None
    assert "type: summary" in issue


def test_subject_from_commit_message_file_skips_comments(tmp_path: Path) -> None:
    commit_file = tmp_path / "COMMIT_EDITMSG"
    commit_file.write_text(
        "\n# Please enter the commit message\nfeat: add commit hook\n\nbody\n",
        encoding="utf-8",
    )

    assert subject_from_commit_message_file(commit_file) == "feat: add commit hook"


def test_validate_commit_subjects_returns_deterministic_errors() -> None:
    issues = validate_commit_subjects(
        [
            "feat: add commit policy",
            "bad message",
            "chore: tighten hooks",
            "refactor: invalid prefix",
        ]
    )

    assert issues == [
        "commit[2] `bad message`: subject must match `type: summary` with allowed types [feat, fix, spec, docs, chore, test]",
        "commit[4] `refactor: invalid prefix`: subject must match `type: summary` with allowed types [feat, fix, spec, docs, chore, test]",
    ]


def test_commit_subjects_from_range_reads_subjects(tmp_path: Path) -> None:
    repo = tmp_path
    _run_git(repo, "init")
    _run_git(repo, "config", "user.name", "test")
    _run_git(repo, "config", "user.email", "test@example.com")

    (repo / "notes.txt").write_text("line 1\n", encoding="utf-8")
    _run_git(repo, "add", "notes.txt")
    _run_git(repo, "commit", "-m", "feat: add notes")

    (repo / "notes.txt").write_text("line 2\n", encoding="utf-8")
    _run_git(repo, "add", "notes.txt")
    _run_git(repo, "commit", "-m", "docs: update notes")

    subjects = commit_subjects_from_range(repo, "HEAD~1..HEAD")
    assert subjects == ["docs: update notes"]


def test_commit_subjects_from_range_raises_for_invalid_range(tmp_path: Path) -> None:
    repo = tmp_path
    _run_git(repo, "init")

    with pytest.raises(ValueError):
        commit_subjects_from_range(repo, "missing-range")
