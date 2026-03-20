"""Root implement command."""

import typer

from developer.application.services.implementation_run_service import (
    run_implementation,
)


def implement(
    plan_path: str = typer.Argument(
        ..., help="Markdown plan path, with or without a leading @"
    ),
    max_iterations: str | None = typer.Option(
        None,
        "--max-iterations",
        help=(
            "Override implementation max iterations with a positive integer or 'infinite'. "
            "CLI overrides config, which overrides the default of 40."
        ),
    ),
) -> None:
    """Run implementation against one markdown plan."""
    result = run_implementation(task_input=plan_path, max_iterations=max_iterations)
    typer.echo(result.message)
    raise typer.Exit(code=result.exit_code)
