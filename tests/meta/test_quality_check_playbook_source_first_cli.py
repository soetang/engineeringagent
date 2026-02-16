from __future__ import annotations

from pathlib import Path

import engineeringagent


def test_quality_check_playbook_uses_source_first_cli(repo_root: Path) -> None:
    assert engineeringagent.__name__ == "engineeringagent"
    path = repo_root / "docs" / "principles" / "quality-check-playbook.md"
    body = path.read_text(encoding="utf-8")

    assert "uv run engineeringagent" not in body
    assert "uv run python -m engineeringagent.cli gates run --profile loop_fast" in body
    assert "uv run python -m engineeringagent.cli gates run --profile precommit" in body
    assert "uv run python -m engineeringagent.cli validate" in body
