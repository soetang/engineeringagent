"""CLI entry point for developer commands."""

import typer

from developer.presentation.commands import check, implementation

app = typer.Typer()
app.add_typer(check.app, name="check")
app.add_typer(implementation.app, name="implementation")

if __name__ == "__main__":
    app()
