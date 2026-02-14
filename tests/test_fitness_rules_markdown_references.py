from __future__ import annotations

from pathlib import Path
from typing import cast

from engineeringagent.fitness.builtin_rules import (
    evaluate_markdown_locality_reference_coverage,
)


def _write_file(project_root: Path, relative_path: str, body: str = "content") -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def test_markdown_reference_coverage_passes_with_non_self_reference(
    tmp_path: Path,
) -> None:
    _write_file(tmp_path, "src/engineeringagent/prompts/templates/loop.md")
    _write_file(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        'TEMPLATE_PATH = "src/engineeringagent/prompts/templates/loop.md"\n',
    )

    result = evaluate_markdown_locality_reference_coverage(tmp_path)

    assert result["status"] == "pass"
    assert _violations(result) == []


def test_markdown_reference_coverage_passes_for_reviewer_prompt_with_reference(
    tmp_path: Path,
) -> None:
    _write_file(tmp_path, "harness/reviewers/prompts/code_simplifier.md")
    _write_file(
        tmp_path,
        "src/engineeringagent/init_scaffold.py",
        'PROMPT_PATH = "harness/reviewers/prompts/code_simplifier.md"\n',
    )

    result = evaluate_markdown_locality_reference_coverage(tmp_path)

    assert result["status"] == "pass"
    assert _violations(result) == []


def test_markdown_reference_coverage_fails_when_non_doc_markdown_is_unreferenced(
    tmp_path: Path,
) -> None:
    _write_file(tmp_path, "README.md")

    result = evaluate_markdown_locality_reference_coverage(tmp_path)
    violations = _violations(result)

    assert result["status"] == "fail"
    assert violations == [
        "README.md:1 markdown file outside docs/ has no in-repo non-self reference; add at least one deterministic path reference from another repository file."
    ]


def test_markdown_reference_coverage_requires_non_self_reference(
    tmp_path: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/scaffold_templates/AGENTS.md",
        "See src/engineeringagent/scaffold_templates/AGENTS.md\n",
    )

    result = evaluate_markdown_locality_reference_coverage(tmp_path)
    violations = _violations(result)

    assert result["status"] == "fail"
    assert violations == [
        "src/engineeringagent/scaffold_templates/AGENTS.md:1 markdown file outside docs/ has no in-repo non-self reference; add at least one deterministic path reference from another repository file."
    ]


def test_markdown_reference_coverage_skips_docs_markdown(tmp_path: Path) -> None:
    _write_file(tmp_path, "docs/reference.md")

    result = evaluate_markdown_locality_reference_coverage(tmp_path)

    assert result["status"] == "pass"
    assert _violations(result) == []


def test_markdown_reference_coverage_ignores_references_from_ignored_directories(
    tmp_path: Path,
) -> None:
    _write_file(tmp_path, "README.md")
    _write_file(tmp_path, "tmp/references.txt", "README.md\n")

    result = evaluate_markdown_locality_reference_coverage(tmp_path)
    violations = _violations(result)

    assert result["status"] == "fail"
    assert violations == [
        "README.md:1 markdown file outside docs/ has no in-repo non-self reference; add at least one deterministic path reference from another repository file."
    ]
