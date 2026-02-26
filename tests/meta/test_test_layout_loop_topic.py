from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("old_relpath", "new_relpath"),
    [
        ("tests/test_loop_contracts.py", "tests/loop/test_loop_contracts.py"),
        (
            "tests/test_loop_opencode_integration.py",
            "tests/loop/test_loop_opencode_integration.py",
        ),
        ("tests/test_loop_output.py", "tests/loop/test_loop_output.py"),
        (
            "tests/test_loop_feature_iteration.py",
            "tests/loop/test_loop_feature_iteration.py",
        ),
        ("tests/test_loop_reviewers.py", "tests/loop/test_loop_reviewers.py"),
        (
            "tests/test_loop_runtime_iteration.py",
            "tests/loop/test_loop_runtime_iteration.py",
        ),
        (
            "tests/test_loop_runtime_time_format.py",
            "tests/loop/test_loop_runtime_time_format.py",
        ),
        ("tests/test_loop_selection.py", "tests/loop/test_loop_selection.py"),
    ],
)
def test_loop_tests_are_grouped_under_topic_folder(
    pytestconfig: pytest.Config,
    old_relpath: str,
    new_relpath: str,
) -> None:
    """Enforce a stable, topic-oriented layout for loop-related tests."""

    repo_root = Path(pytestconfig.rootpath)

    assert (repo_root / new_relpath).is_file(), f"missing moved test: {new_relpath}"
    assert not (repo_root / old_relpath).exists(), (
        f"unexpected root test: {old_relpath}"
    )
