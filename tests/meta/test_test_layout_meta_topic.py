from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("old_relpath", "new_relpath"),
    [
        ("tests/test_coverage_misc.py", "tests/meta/test_coverage_misc.py"),
        (
            "tests/test_coverage_threshold_regressions.py",
            "tests/meta/test_coverage_threshold_regressions.py",
        ),
        (
            "tests/test_spec_writing_reference_doc.py",
            "tests/meta/test_spec_writing_reference_doc.py",
        ),
        ("tests/test_validator.py", "tests/meta/test_validator.py"),
    ],
)
def test_meta_tests_are_grouped_under_topic_folder(
    pytestconfig: pytest.Config,
    old_relpath: str,
    new_relpath: str,
) -> None:
    """Enforce a stable, topic-oriented layout for repo meta/contract tests."""

    repo_root = Path(pytestconfig.rootpath)

    assert (repo_root / new_relpath).is_file(), f"missing moved test: {new_relpath}"
    assert not (repo_root / old_relpath).exists(), (
        f"unexpected root test: {old_relpath}"
    )
