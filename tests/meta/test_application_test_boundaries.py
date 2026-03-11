from __future__ import annotations

from pathlib import Path

import pytest


def test_application_tests_do_not_import_adapters(
    pytestconfig: pytest.Config,
) -> None:
    """Application-layer tests should exercise application services through ports."""

    repo_root = Path(pytestconfig.rootpath)
    tests_root = repo_root / "tests" / "application"
    offending: list[str] = []

    for test_path in sorted(tests_root.rglob("test_*.py")):
        source = test_path.read_text(encoding="utf-8")
        if "engineeringagent.adapters" not in source:
            continue
        offending.append(test_path.relative_to(repo_root).as_posix())

    assert offending == [], (
        "application tests must not import adapters directly; "
        f"use ports or test doubles instead: {', '.join(offending)}"
    )
