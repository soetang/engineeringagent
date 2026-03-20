"""Tests for the validate-plan CLI command."""

from pathlib import Path

from typer.testing import CliRunner

from developer.presentation.cli import app


def _write_plan(
    path: Path, *, status: str = "ready", phase_status: str = "todo"
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def test_validate_plan_command_succeeds_for_valid_plan() -> None:
    """Validation command should succeed for a valid plan."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_plan(Path("docs/plans/ship-it.md"))
        result = runner.invoke(app, ["validate-plan", "docs/plans/ship-it.md"])

    assert result.exit_code == 0
    assert "Plan validation successful: docs/plans/ship-it.md" in result.output


def test_validate_plan_command_accepts_at_prefixed_path() -> None:
    """Validation command should accept @-prefixed paths."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_plan(Path("docs/plans/ship-it.md"))
        result = runner.invoke(app, ["validate-plan", "@docs/plans/ship-it.md"])

    assert result.exit_code == 0
    assert "Plan validation successful: docs/plans/ship-it.md" in result.output


def test_validate_plan_command_prints_actionable_errors() -> None:
    """Validation command should surface semantic plan errors."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_plan(Path("docs/plans/ship-it.md"), status="done", phase_status="todo")
        result = runner.invoke(app, ["validate-plan", "docs/plans/ship-it.md"])

    assert result.exit_code == 1
    assert "Plan validation failed: docs/plans/ship-it.md" in result.output
    assert "all phases are 'done'" in result.output
