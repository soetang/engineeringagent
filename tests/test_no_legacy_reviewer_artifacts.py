from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


NEEDLES = (
    b"approval" + b".mode",
    b"passed" + b":advisory",
    b"reviewer" + b"_advisory_followup",
    b"blocking" + b"_exhausted",
    b"continue" + b"_on_exhausted",
    b"advisory" + b"_followup_required",
)

ALLOW = "docs/spec/features/FEAT-086-simplify-feature-done-reviewers-and-rename-next-action.yaml"


def test_repository_removes_legacy_reviewer_artifacts(
    pytestconfig: pytest.Config,
) -> None:
    repo_root = Path(pytestconfig.rootpath)
    files = subprocess.check_output(
        ["git", "ls-files"], cwd=repo_root, text=True
    ).splitlines()
    hits: list[str] = []
    for file in files:
        if file == ALLOW:
            continue
        if file.startswith("docs/spec/features_done/"):
            continue
        path = repo_root / file
        if not path.exists():
            continue
        data = path.read_bytes()
        if any(needle in data for needle in NEEDLES):
            hits.append(file)

    assert hits == [], "legacy reviewer artifacts found:\n" + "\n".join(hits)
