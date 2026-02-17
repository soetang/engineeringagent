from __future__ import annotations

from pathlib import Path


def test_loop_and_reviewers_use_progress_subpackage(repo_root: Path) -> None:
    # This feature refactors progress helpers into the shared
    # `engineeringagent.progress` subpackage. Keep the old top-level modules as
    # shims if needed, but core modules should import the new canonical paths.
    targets = [
        repo_root / "src" / "engineeringagent" / "loop_runtime" / "telemetry.py",
        repo_root / "src" / "engineeringagent" / "loop_runtime" / "implement.py",
        repo_root / "src" / "engineeringagent" / "reviewers.py",
    ]

    forbidden = [
        "engineeringagent.progress_paths",
        "engineeringagent.progress_logging",
        "from engineeringagent import progress_paths",
        "from engineeringagent import progress_logging",
    ]

    violations: list[str] = []
    for path in targets:
        body = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in body:
                violations.append(f"{path.as_posix()}: contains {token!r}")

    assert not violations, "Legacy progress helper imports remain:\n" + "\n".join(
        violations
    )
