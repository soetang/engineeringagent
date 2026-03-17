"""Check command for validation and execution."""

import typer
from developer.quality.services.validation_service import ValidationService
from developer.quality.services.execution_service import ExecutionService

app = typer.Typer()


@app.command()
def validate():
    """Validate the schema of checks.yaml and referenced files."""
    typer.echo("Validating check configurations...")

    # Initialize validation service
    validation_service = ValidationService()

    # Validate the checks.yaml file (uses config-based path)
    result = validation_service.validate_checks_yaml()

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


@app.command()
def run():
    """Execute all quality checks defined in harness/checks.yaml."""
    typer.echo("Running quality checks...")

    # Initialize execution service
    execution_service = ExecutionService()

    # Execute the checks (uses config-based path)
    result = execution_service.execute_checks()

    if result["success"]:
        typer.echo(typer.style("✓ All checks passed!", typer.colors.GREEN))
    else:
        typer.echo(typer.style("✗ Some checks failed!", typer.colors.RED))

    typer.echo(result["message"])

    # Show detailed results
    for check_result in result.get("results", []):
        status_color = (
            typer.colors.GREEN if check_result["success"] else typer.colors.RED
        )
        status_symbol = "✓" if check_result["success"] else "✗"

        typer.echo(
            f"  {status_symbol} {check_result['name']}: {check_result['status']}"
        )
        if check_result["message"]:
            typer.echo(f"    {check_result['message']}")

    raise typer.Exit(code=0 if result["success"] else 1)
