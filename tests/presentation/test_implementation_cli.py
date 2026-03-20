"""Tests for the implement CLI command."""

from typer.testing import CliRunner

from developer.application.models import ImplementationRunResult
from developer.presentation.cli import app


def test_implement_command_calls_service_with_plan_path(monkeypatch) -> None:
    """The command should pass the plan path through to the application service."""
    calls: list[tuple[str, str | None]] = []

    def fake_run_implementation(task_input: str, max_iterations: str | None = None):
        calls.append((task_input, max_iterations))
        return ImplementationRunResult(
            exit_code=0,
            message="Implementation run succeeded",
        )

    monkeypatch.setattr(
        "developer.presentation.commands.implement.run_implementation",
        fake_run_implementation,
    )

    result = CliRunner().invoke(app, ["implement", "docs/plans/ship-it.md"])

    assert result.exit_code == 0
    assert result.output == "Implementation run succeeded\n"
    assert calls == [("docs/plans/ship-it.md", None)]


def test_implement_command_uses_workspace_flow_when_configured(monkeypatch) -> None:
    """The root command should pass through the max-iterations override."""
    runner = CliRunner()

    monkeypatch.setattr(
        "developer.presentation.commands.implement.run_implementation",
        lambda task_input, max_iterations=None: ImplementationRunResult(
            exit_code=0,
            message=(
                f"workspace=workspace-1 run=run-1 task={task_input} "
                f"status=succeeded max_iterations={max_iterations}"
            ),
        ),
    )

    result = runner.invoke(
        app,
        ["implement", "docs/plans/ship-it.md", "--max-iterations", "20"],
    )

    assert result.exit_code == 0
    assert "task=docs/plans/ship-it.md" in result.output
    assert "max_iterations=20" in result.output


def test_implement_command_requires_plan_path() -> None:
    """The implement command should require a positional plan path."""
    runner = CliRunner()

    result = runner.invoke(app, ["implement"])

    assert result.exit_code != 0
    assert "Missing argument 'PLAN_PATH'" in result.output
