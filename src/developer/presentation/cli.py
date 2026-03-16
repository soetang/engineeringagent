"""CLI entry point for the quality package."""

import typer

from developer.presentation.commands import check

app = typer.Typer()
app.add_typer(check.app, name="check")

if __name__ == "__main__":
    app()
