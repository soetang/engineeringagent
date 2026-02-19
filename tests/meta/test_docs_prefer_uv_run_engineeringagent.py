from __future__ import annotations

from pathlib import Path


def test_operational_docs_prefer_uv_run_engineeringagent(repo_root: Path) -> None:
    paths = [
        repo_root / "AGENTS.md",
        repo_root / "docs" / "references" / "quality-check-playbook.md",
        repo_root / "docs" / "references" / "reviewer-authoring-guide.md",
        repo_root / "docs" / "references" / "docs-architecture.md",
        repo_root / "docs" / "references" / "retry-feedback.md",
        repo_root / "docs" / "references" / "reviewer-agents.md",
        repo_root / "docs" / "references" / "uv-workflow.md",
        repo_root
        / "src"
        / "engineeringagent"
        / "prompts"
        / "templates"
        / "loop_implementation.md",
        repo_root
        / "src"
        / "engineeringagent"
        / "scaffold_templates"
        / "reference.docs-architecture.md",
        repo_root / "src/engineeringagent/scaffold_templates/reference.workflow.md",
    ]

    for path in paths:
        assert path.exists()
