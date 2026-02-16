from __future__ import annotations

from pathlib import Path

import pytest


def test_test_modules_do_not_compute_repo_root_via_parents_1(
    pytestconfig: pytest.Config,
) -> None:
    """Keep repo-root resolution stable when tests move into topic folders.

    `Path(__file__).resolve().parents[1]` is brittle: it changes once tests live one
    directory deeper (e.g. `tests/fitness/test_*.py`). Prefer `pytestconfig.rootpath`
    (directly or via a fixture).
    """

    repo_root = Path(pytestconfig.rootpath)
    tests_root = repo_root / "tests"

    # Avoid embedding the exact substring in this file (we scan source text).
    disallowed = "Path(__file__).resolve().parents[" + "1]"

    offenders: list[str] = []
    for path in sorted(tests_root.rglob("test_*.py")):
        if path == Path(__file__).resolve():
            continue

        relpath = path.relative_to(repo_root).as_posix()
        if disallowed in path.read_text(encoding="utf-8"):
            offenders.append(relpath)

    assert not offenders, (
        "brittle repo-root resolution found; replace with pytestconfig.rootpath/"
        f"repo_root fixture: {', '.join(offenders)}"
    )
