"""Tests for the markdown plan loader service."""

import pytest

from developer.tasks.errors import TaskPlanValidationError
from developer.tasks.services.markdown_plan_loader import MarkdownPlanLoader


def _write_plan(path, *, status: str = "ready", phase_status: str = "todo") -> None:
    path.write_text(
        f"""---
schema_version: 1
task_id: ship-it
title: Ship it
status: {status}
phases:
  - id: build
    title: Build
    status: {phase_status}
---
""",
        encoding="utf-8",
    )


def test_markdown_plan_loader_loads_definition(tmp_path) -> None:
    """Loader should return a typed plan definition for valid plans."""
    plan_path = tmp_path / "plan.md"
    _write_plan(plan_path)

    definition = MarkdownPlanLoader().load_definition(str(plan_path))

    assert definition.task_id == "ship-it"
    assert definition.title == "Ship it"
    assert definition.path == str(plan_path.resolve())


def test_markdown_plan_loader_returns_validation_errors(tmp_path) -> None:
    """Loader validation should return semantic errors without raising."""
    plan_path = tmp_path / "plan.md"
    _write_plan(plan_path, status="done", phase_status="todo")

    result = MarkdownPlanLoader().validate(str(plan_path))

    assert result.valid is False
    assert any("all phases are 'done'" in error.message for error in result.errors)


def test_markdown_plan_loader_raises_for_invalid_definition(tmp_path) -> None:
    """Loader should raise a formatted validation error for invalid plans."""
    plan_path = tmp_path / "plan.md"
    _write_plan(plan_path, status="done", phase_status="todo")

    with pytest.raises(TaskPlanValidationError, match="Plan validation failed"):
        MarkdownPlanLoader().load_definition(str(plan_path))
