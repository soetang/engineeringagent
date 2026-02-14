from __future__ import annotations

from pathlib import Path
from typing import cast

from engineeringagent.fitness.builtin_rules import (
    MARKDOWN_LOCALITY_REFERENCE_COVERAGE_RULE_ID,
    evaluate_markdown_locality_reference_coverage,
)


def _write_markdown(
    project_root: Path, relative_path: str, body: str = "content"
) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def test_markdown_locality_rule_uses_expected_rule_id() -> None:
    """Expose the stable built-in rule id for markdown locality checks."""
    assert (
        MARKDOWN_LOCALITY_REFERENCE_COVERAGE_RULE_ID
        == "architecture.markdown-locality-reference-coverage"
    )


def test_markdown_locality_rule_passes_for_approved_markdown_locations(
    tmp_path: Path,
) -> None:
    """Pass when markdown files remain in approved roots and root exceptions."""
    _write_markdown(tmp_path, "docs/guide.md")
    _write_markdown(tmp_path, "src/engineeringagent/prompts/templates/loop.md")
    _write_markdown(tmp_path, "src/engineeringagent/scaffold_templates/AGENTS.md")
    _write_markdown(tmp_path, "README.md")
    _write_markdown(tmp_path, "AGENTS.md")
    _write_markdown(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        (
            'PROMPT_TEMPLATE = "src/engineeringagent/prompts/templates/loop.md"\n'
            'README_PATH = "README.md"\n'
            'AGENTS_PATH = "AGENTS.md"\n'
            'SCAFFOLD_PATH = "src/engineeringagent/scaffold_templates/AGENTS.md"\n'
        ),
    )

    result = evaluate_markdown_locality_reference_coverage(tmp_path)

    assert result["status"] == "pass"
    assert _violations(result) == []


def test_markdown_locality_rule_fails_for_markdown_outside_approved_roots(
    tmp_path: Path,
) -> None:
    """Fail with path:line diagnostics for out-of-policy markdown files."""
    _write_markdown(tmp_path, "CHANGELOG.md")
    _write_markdown(tmp_path, "notes/design.md")
    _write_markdown(tmp_path, "docs/refs.md", "CHANGELOG.md\nnotes/design.md\n")

    result = evaluate_markdown_locality_reference_coverage(tmp_path)
    violations = _violations(result)

    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert violations[0].startswith("CHANGELOG.md:1")
    assert violations[1].startswith("notes/design.md:1")
    assert all(
        "outside approved locality roots" in violation for violation in violations
    )


def test_markdown_locality_rule_ignores_generated_and_cache_directories(
    tmp_path: Path,
) -> None:
    """Skip markdown files under ignored directories during locality discovery."""
    _write_markdown(tmp_path, "tmp/notes.md")
    _write_markdown(tmp_path, "dist/output.md")
    _write_markdown(tmp_path, ".venv/docs.md")
    _write_markdown(tmp_path, ".pytest_cache/cache.md")
    _write_markdown(tmp_path, "__pycache__/cache.md")

    result = evaluate_markdown_locality_reference_coverage(tmp_path)

    assert result["status"] == "pass"
    assert _violations(result) == []


def test_markdown_locality_rule_ignores_tooling_and_vendor_directories(
    tmp_path: Path,
) -> None:
    """Skip markdown files under tool-state and vendored dependency directories."""
    _write_markdown(tmp_path, ".opencode/agents/build.md")
    _write_markdown(tmp_path, ".opencode/node_modules/zod/README.md")

    result = evaluate_markdown_locality_reference_coverage(tmp_path)

    assert result["status"] == "pass"
    assert _violations(result) == []
