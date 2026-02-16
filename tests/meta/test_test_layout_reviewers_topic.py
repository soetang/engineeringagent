from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("old_relpath", "new_relpath"),
    [
        (
            "tests/test_repo_reviewers_config.py",
            "tests/reviewers/test_repo_reviewers_config.py",
        ),
        (
            "tests/test_reviewers_contract.py",
            "tests/reviewers/test_reviewers_contract.py",
        ),
        ("tests/test_reviewers_parse.py", "tests/reviewers/test_reviewers_parse.py"),
        (
            "tests/test_reviewers_runtime.py",
            "tests/reviewers/test_reviewers_runtime.py",
        ),
        (
            "tests/test_reviewers_sandbox.py",
            "tests/reviewers/test_reviewers_sandbox.py",
        ),
        ("tests/test_reviewers_state.py", "tests/reviewers/test_reviewers_state.py"),
    ],
)
def test_reviewer_tests_are_grouped_under_topic_folder(
    pytestconfig: pytest.Config,
    old_relpath: str,
    new_relpath: str,
) -> None:
    """Enforce a stable, topic-oriented layout for reviewer tests."""

    repo_root = Path(pytestconfig.rootpath)

    assert (repo_root / new_relpath).is_file(), f"missing moved test: {new_relpath}"
    assert not (repo_root / old_relpath).exists(), (
        f"unexpected root test: {old_relpath}"
    )
