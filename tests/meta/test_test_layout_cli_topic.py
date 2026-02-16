from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("old_relpath", "new_relpath"),
    [
        ("tests/test_cli.py", "tests/cli/test_cli.py"),
        ("tests/test_cli_reviewers.py", "tests/cli/test_cli_reviewers.py"),
        (
            "tests/test_cli_typer_parity_helpers.py",
            "tests/cli/test_cli_typer_parity_helpers.py",
        ),
        ("tests/test_init_command.py", "tests/cli/test_init_command.py"),
        ("tests/test_init_scaffold.py", "tests/cli/test_init_scaffold.py"),
    ],
)
def test_cli_tests_are_grouped_under_topic_folder(
    pytestconfig: pytest.Config,
    old_relpath: str,
    new_relpath: str,
) -> None:
    """Enforce a stable, topic-oriented layout for CLI-related tests."""

    repo_root = Path(pytestconfig.rootpath)

    assert (repo_root / new_relpath).is_file(), f"missing moved test: {new_relpath}"
    assert not (repo_root / old_relpath).exists(), (
        f"unexpected root test: {old_relpath}"
    )
