from __future__ import annotations

from pathlib import Path


def test_fitness_docs_describe_supported_harness_helper_surface(
    repo_root: Path,
) -> None:
    doc_path = repo_root / "docs" / "fitness-functions" / "README.md"
    markdown = doc_path.read_text(encoding="utf-8")

    required_fragments = [
        "## Harness Authoring Surface",
        "`engineeringagent.fitness.*`",
        "`engineeringagent.fitness.envelope`",
        "emit_result_envelope",
        "must not import",
    ]

    missing = [fragment for fragment in required_fragments if fragment not in markdown]
    assert not missing, (
        "missing fragments in docs/fitness-functions/README.md: " + ", ".join(missing)
    )
