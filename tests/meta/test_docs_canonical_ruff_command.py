from __future__ import annotations

from pathlib import Path


def test_docs_reference_canonical_ruff_command_includes_harness(
    repo_root: Path,
) -> None:
    paths = [
        repo_root / "docs" / "references" / "uv-llms.md",
        repo_root / "docs" / "references" / "python-uv-ruff-llms.md",
        repo_root / "docs" / "principles" / "quality-check-playbook.md",
    ]
    expected = "uv run ruff check src/engineeringagent harness"

    for path in paths:
        body = path.read_text(encoding="utf-8")
        assert expected in body, f"{path} must mention: {expected}"
