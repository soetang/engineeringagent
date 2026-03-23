"""Plan validation CLI command."""

from pathlib import Path

import typer

from developer.application.services.plan_service import (
    validate_plan as validate_task_plan,
)


def _display_plan_path(plan_path: str) -> str:
    """Return the user-facing plan path without the optional @ prefix."""
    if plan_path.startswith("@"):
        return plan_path[1:]
    return plan_path


def validate_plan(
    plan_path: str = typer.Argument(
        ..., help="Markdown plan path, with or without a leading @"
    ),
) -> None:
    """Validate one markdown task plan."""
    result = validate_task_plan(plan_path, base_path=Path.cwd())
    normalized_path = _display_plan_path(plan_path)
    if result.valid:
        typer.echo(f"Plan validation successful: {normalized_path}")
        raise typer.Exit(code=0)
    typer.echo(f"Plan validation failed: {normalized_path}")
    for error in result.errors:
        typer.echo(f"- {error.location}: {error.message}")
    raise typer.Exit(code=1)
