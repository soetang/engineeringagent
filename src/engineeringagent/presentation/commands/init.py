"""Interactive repository onboarding command."""

import typer

from engineeringagent.application.services.init_service import initialize_repository
from engineeringagent.scaffolding.models import InitRequest


def init() -> None:
    """Scaffold a minimal engineeringagent onboarding setup."""
    harness_dir = (
        typer.prompt("Harness directory", default="harness").strip() or "harness"
    )
    create_or_update_config = typer.confirm(
        "Create or update engineeringagent.toml?",
        default=True,
    )
    create_or_append_agents_md = typer.confirm(
        "Create or append AGENTS.md guidance?",
        default=True,
    )

    result = initialize_repository(
        InitRequest(
            harness_dir=harness_dir,
            create_or_update_config=create_or_update_config,
            create_or_append_agents_md=create_or_append_agents_md,
        )
    )

    typer.echo(
        f"Scaffolded repository for harness directory: {result.harness_dir.name}"
    )
    for file_result in result.file_results:
        line = f"{file_result.status.upper():<7} {file_result.path}"
        if file_result.reason:
            line = f"{line} ({file_result.reason})"
        typer.echo(line)
