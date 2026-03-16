"""Check command for validation."""

import typer
from developer.quality.services.validation_service import ValidationService

app = typer.Typer()


@app.command()
def run():
    """Run validation checks using harness/checks.yaml."""
    typer.echo("Running validation checks...")

    # Initialize validation service
    validation_service = ValidationService()

    # Validate the checks.yaml file
    result = validation_service.validate_checks_yaml("harness/checks.yaml")

    if result["valid"]:
        typer.echo(typer.style("✓ Validation successful!", typer.colors.GREEN))
        typer.echo(result["message"])

        # Show validated checks
        for check_item in result.get("checks", []):
            typer.echo(f"  - {check_item['name']}: {check_item['filepath']}")
    else:
        typer.echo(typer.style("✗ Validation failed!", typer.colors.RED))
        typer.echo(result["message"])
        raise typer.Exit(code=1)
