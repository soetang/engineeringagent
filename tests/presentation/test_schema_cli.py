"""Tests for the schema CLI commands."""

import json

from typer.testing import CliRunner

from engineeringagent.presentation.cli import app


def test_schema_plan_outputs_frontmatter_schema() -> None:
    """Plan schema command should expose the frontmatter contract."""
    runner = CliRunner()

    result = runner.invoke(app, ["schema", "plan"])

    assert result.exit_code == 0

    schema = json.loads(result.output)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["properties"]["status"]["enum"] == [
        "draft",
        "ready",
        "in_progress",
        "blocked",
        "done",
    ]
    assert schema["properties"]["phases"]["minItems"] == 1
    assert "path" not in schema["properties"]
    assert schema["required"] == [
        "schema_version",
        "task_id",
        "title",
        "status",
        "phases",
    ]


def test_schema_quality_outputs_quality_schema() -> None:
    """Quality schema command should expose the dynamic quality contract."""
    runner = CliRunner()

    result = runner.invoke(app, ["schema", "quality"])

    assert result.exit_code == 0

    schema = json.loads(result.output)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["checks"]["type"] == "array"
    assert "checks" in schema["required"]
    assert "$defs" in schema
    assert "CommandCheck" in schema["$defs"]
