"""CLI entry point for engineeringagent commands."""

import typer

from engineeringagent.presentation.commands import check
from engineeringagent.presentation.commands.init import init
from engineeringagent.presentation.commands.implement import implement
from engineeringagent.presentation.commands.plan import validate_plan
from engineeringagent.presentation.commands.schema import app as schema_app

app = typer.Typer()
app.add_typer(check.app, name="check")
app.add_typer(schema_app, name="schema")
app.command(name="init")(init)
app.command(name="implement")(implement)
app.command(name="validate-plan")(validate_plan)

if __name__ == "__main__":
    app()
