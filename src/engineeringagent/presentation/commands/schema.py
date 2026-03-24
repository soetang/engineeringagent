"""Schema export CLI commands."""

import json

import typer

from engineeringagent.application.services.schema_service import (
    get_plan_schema,
    get_quality_schema,
)

app = typer.Typer(help="Export machine-readable schemas.")


def _emit_schema(schema: dict[str, object]) -> None:
    """Write schema JSON to stdout with stable formatting."""
    typer.echo(json.dumps(schema, indent=2, sort_keys=True))


@app.command("plan")
def export_plan_schema() -> None:
    """Export the JSON Schema for plan frontmatter."""
    _emit_schema(get_plan_schema())


@app.command("quality")
def export_quality_schema() -> None:
    """Export the JSON Schema for quality YAML."""
    _emit_schema(get_quality_schema())
