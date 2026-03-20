"""Tests for markdown plan parsing."""

import pytest

from developer.tasks.errors import TaskPlanLoadError
from developer.tasks.services.markdown_plan_parser import MarkdownPlanParser


def test_markdown_plan_parser_parses_frontmatter_and_body(tmp_path) -> None:
    """Parser should return frontmatter, body, and canonical path."""
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        """---
schema_version: 1
task_id: ship-it
title: Ship it
status: ready
phases:
  - id: build
    title: Build
    status: todo
---

# Goal

Do the thing.
""",
        encoding="utf-8",
    )

    frontmatter, body, canonical_path = MarkdownPlanParser().parse(str(plan_path))

    assert frontmatter["task_id"] == "ship-it"
    assert "# Goal" in body
    assert canonical_path == str(plan_path.resolve())


def test_markdown_plan_parser_requires_frontmatter(tmp_path) -> None:
    """Parser should fail clearly when frontmatter is missing."""
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# No frontmatter\n", encoding="utf-8")

    with pytest.raises(TaskPlanLoadError, match="missing YAML frontmatter"):
        MarkdownPlanParser().parse(str(plan_path))


def test_markdown_plan_parser_rejects_malformed_yaml(tmp_path) -> None:
    """Parser should fail clearly when YAML is malformed."""
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        """---
schema_version: [
---
""",
        encoding="utf-8",
    )

    with pytest.raises(TaskPlanLoadError, match="Malformed YAML frontmatter"):
        MarkdownPlanParser().parse(str(plan_path))
