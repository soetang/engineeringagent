from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("old_relpath", "new_relpath"),
    [
        ("tests/test_opencode_client.py", "tests/opencode/test_opencode_client.py"),
        (
            "tests/test_opencode_permissions.py",
            "tests/opencode/test_opencode_permissions.py",
        ),
    ],
)
def test_opencode_tests_are_grouped_under_topic_folder(
    pytestconfig: pytest.Config,
    old_relpath: str,
    new_relpath: str,
) -> None:
    """Enforce a stable, topic-oriented layout for opencode-related tests."""

    repo_root = Path(pytestconfig.rootpath)

    assert (repo_root / new_relpath).is_file(), f"missing moved test: {new_relpath}"
    assert not (repo_root / old_relpath).exists(), (
        f"unexpected root test: {old_relpath}"
    )
