from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PATH = REPO_ROOT / "docs" / "references" / "spec-writing-llms.md"
TEMPLATE_PATH = (
    REPO_ROOT
    / "src"
    / "engineeringagent"
    / "scaffold_templates"
    / "reference.spec-writing-llms.md"
)


def test_spec_writing_reference_uses_supported_validate_command() -> None:
    body = CANONICAL_PATH.read_text(encoding="utf-8")

    assert "scripts/validate_specs.py" not in body
    assert "engineeringagent validate" in body


def test_spec_writing_reference_is_exact_sync_with_scaffold_template() -> None:
    assert CANONICAL_PATH.read_bytes() == TEMPLATE_PATH.read_bytes()
