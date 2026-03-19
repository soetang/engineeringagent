"""Implementation command group."""

import typer

from developer.application.services.implementation_run_service import (
    run_implementation,
)

app = typer.Typer()


@app.command()
def run() -> None:
    """Run the implementation agent."""
    result = run_implementation()
    typer.echo(result.message)
    raise typer.Exit(code=result.exit_code)
