from __future__ import annotations

from pathlib import Path


def test_agent_facing_docs_prefer_uv_run_engineeringagent(repo_root: Path) -> None:
    paths = [
        repo_root / "AGENTS.md",
        repo_root / "docs" / "principles" / "quality-check-playbook.md",
        repo_root / "docs" / "principles" / "reviewer-authoring-guide.md",
        repo_root / "docs" / "references" / "docs-architecture-llms.md",
        repo_root / "docs" / "references" / "retry-feedback-llms.md",
        repo_root / "docs" / "references" / "reviewer-agents-llms.md",
        repo_root / "docs" / "references" / "uv-llms.md",
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
        / "reference.docs-architecture-llms.md",
    ]

    forbidden = "uv run python -m engineeringagent.cli"
    required = "uv run engineeringagent"

    for path in paths:
        body = path.read_text(encoding="utf-8")
        assert forbidden not in body, f"{path} must not mention: {forbidden}"
        assert required in body, f"{path} must mention: {required}"
