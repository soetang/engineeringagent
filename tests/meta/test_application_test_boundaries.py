from __future__ import annotations

from pathlib import Path


def test_application_tests_do_not_import_adapters() -> None:
    """Application-layer tests should exercise application services through ports."""

    tests_root = Path(__file__).resolve().parents[1] / "application"
    offending: list[str] = []

    for test_path in sorted(tests_root.rglob("test_*.py")):
        source = test_path.read_text(encoding="utf-8")
        if "engineeringagent.adapters" not in source:
            continue
        offending.append(test_path.relative_to(Path(__file__).resolve().parents[2]).as_posix())

    assert offending == [], (
        "application tests must not import adapters directly; "
        f"use ports or test doubles instead: {', '.join(offending)}"
    )
