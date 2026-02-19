from __future__ import annotations

from pathlib import Path


def test_docs_reference_canonical_ruff_command_includes_harness(
    repo_root: Path,
) -> None:
    paths = [
        repo_root / "docs" / "references" / "uv-workflow.md",
        repo_root / "docs" / "references" / "python-uv-ruff.md",
        repo_root / "docs" / "references" / "quality-check-playbook.md",
    ]

    for path in paths:
        assert path.exists()
