"""CLI entry point for developer commands."""

import typer

from developer.presentation.commands import check
from developer.presentation.commands.implement import implement
from developer.presentation.commands.plan import validate_plan
from developer.presentation.commands.schema import app as schema_app

app = typer.Typer()
app.add_typer(check.app, name="check")
app.add_typer(schema_app, name="schema")
app.command(name="implement")(implement)
app.command(name="validate-plan")(validate_plan)

if __name__ == "__main__":
    app()
