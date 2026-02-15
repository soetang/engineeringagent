from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _extract_yaml_fence(markdown: str, *, heading: str) -> str:
    """Extract the next ```yaml fenced block after the given heading."""
    start = markdown.find(heading)
    if start == -1:
        raise AssertionError(f"missing heading in markdown: {heading!r}")

    fence_start = markdown.find("```yaml", start)
    if fence_start == -1:
        raise AssertionError(f"missing ```yaml fence after heading: {heading!r}")

    body_start = markdown.find("\n", fence_start)
    if body_start == -1:
        raise AssertionError("unterminated yaml fence header")
    body_start += 1

    fence_end = markdown.find("```", body_start)
    if fence_end == -1:
        raise AssertionError("unterminated yaml fence body")

    return markdown[body_start:fence_end]


def test_reviewer_agents_reference_copy_pastable_examples_are_valid_yaml() -> None:
    doc_path = REPO_ROOT / "docs" / "references" / "reviewer-agents-llms.md"
    markdown = doc_path.read_text(encoding="utf-8")

    v1_example_yaml = _extract_yaml_fence(markdown, heading="Copy-pastable v1 example:")
    v1_example = yaml.safe_load(v1_example_yaml)
    assert isinstance(v1_example, dict)
    assert v1_example.get("contract_version") == "1.0"
    assert v1_example.get("profiles", {}).get("loop_fast") == [
        "code_simplifier",
        "readme_process",
    ]
    assert set(v1_example.get("reviewers", {}).keys()) >= {
        "code_simplifier",
        "readme_process",
    }

    simplifier_yaml = _extract_yaml_fence(
        markdown, heading="Copy-pastable `code_simplifier` entry:"
    )
    simplifier = yaml.safe_load(simplifier_yaml)
    assert isinstance(simplifier, dict)
    assert list(simplifier.keys()) == ["code_simplifier"]
    assert isinstance(simplifier["code_simplifier"], dict)
    assert simplifier["code_simplifier"].get("prompt_file")
