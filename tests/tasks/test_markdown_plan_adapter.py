"""Tests for markdown plan adapter resolution."""

import pytest

from developer.orchestrators.loop.models import CompletionResult
from developer.tasks.adapters.markdown_plan_adapter import MarkdownPlanAdapter
from developer.tasks.errors import TaskPlanLoadError
from developer.tasks.select_service import TaskSelectionService


def _write_plan(
    path,
    *,
    status: str = "ready",
    phase_status: str = "todo",
    base_branch: str | None = None,
) -> None:
    base_branch_line = f"base_branch: {base_branch}\n" if base_branch else ""
    path.write_text(
        f"""---
schema_version: 1
task_id: ship-it
title: Ship it
status: {status}
{base_branch_line}phases:
  - id: build
    title: Build
    status: {phase_status}
---
""",
        encoding="utf-8",
    )


def test_markdown_plan_adapter_resolves_task_and_defaults_branch(tmp_path) -> None:
    """Adapter should resolve a markdown plan into a concrete task."""
    plan_path = tmp_path / "plan.md"
    _write_plan(plan_path)

    task = MarkdownPlanAdapter().resolve(str(plan_path))

    assert task.task_id == "ship-it"
    assert task.task_name == "Ship it"
    assert task.task_path == str(plan_path.resolve())
    assert task.base_branch is None
    assert task.get_branch_name() == "ship-it"


def test_markdown_plan_adapter_exposes_base_branch_from_frontmatter(tmp_path) -> None:
    """Resolved tasks should surface the plan-defined base branch preference."""
    plan_path = tmp_path / "plan.md"
    _write_plan(plan_path, base_branch="develop")

    task = MarkdownPlanAdapter().resolve(str(plan_path))

    assert task.base_branch == "develop"


def test_markdown_plan_task_reloads_completion_from_disk(tmp_path) -> None:
    """Completion checks should reflect the latest file contents."""
    plan_path = tmp_path / "plan.md"
    _write_plan(plan_path, status="in_progress", phase_status="todo")
    task = MarkdownPlanAdapter().resolve(str(plan_path))

    assert task.is_complete() == CompletionResult.INCOMPLETE

    _write_plan(plan_path, status="done", phase_status="done")

    assert task.is_complete() == CompletionResult.COMPLETE


def test_task_selection_service_rejects_unsupported_extension(tmp_path) -> None:
    """Selector should fail clearly for unsupported task inputs."""
    plan_path = tmp_path / "plan.txt"
    plan_path.write_text("not a plan", encoding="utf-8")

    with pytest.raises(TaskPlanLoadError, match="Unsupported task input"):
        TaskSelectionService().resolve(str(plan_path))


def test_markdown_plan_adapter_rejects_missing_file(tmp_path) -> None:
    """Adapter should fail clearly when the plan file is missing."""
    missing_path = tmp_path / "missing.md"

    with pytest.raises(TaskPlanLoadError, match="Plan file not found"):
        MarkdownPlanAdapter().resolve(str(missing_path))
