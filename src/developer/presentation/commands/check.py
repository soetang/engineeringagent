"""Check command for validation and execution."""

from typing import Any

import typer
from developer.orchestrator.models import GatePhase

from developer.quality.services.validation_service import ValidationService
from developer.quality.services import CheckGateRunner

app = typer.Typer()


def _format_status(result: dict[str, Any]) -> str:
    """Render a status icon and label from a check result entry."""
    if result.get("status") == "ERROR":
        return typer.style("✗", typer.colors.RED)
    if result.get("status") == "WARNING":
        return typer.style("!", typer.colors.YELLOW)

    success = result.get("success", False)
    if success:
        return typer.style("✓", typer.colors.GREEN)

    return typer.style("✗", typer.colors.RED)


def _format_check_entry(result: dict[str, Any], index: int) -> str:
    """Return one display line for a single executed check."""
    status = _format_status(result)
    name = result.get("name", "Unnamed check")
    message = result.get("message")
    file_path = result.get("filepath")

    check_type = result.get("check_type")
    if check_type:
        label = f"[{check_type}] {name}"
    else:
        label = str(name)

    if file_path:
        label = f"{label} ({file_path})"

    if message:
        return f"{index:>3}. {status} {label}\n        {message}"

    return f"{index:>3}. {status} {label}"


@app.command()
def validate() -> None:
    """Validate the schema of checks.yaml and referenced files."""
    typer.echo("Validating check configurations...")

    validation_service = ValidationService()

    result = validation_service.validate_checks_yaml()

    if not result["valid"]:
        typer.echo(typer.style("✗ Validation failed!", typer.colors.RED))
        typer.echo(result["message"])
        raise typer.Exit(code=1)

    typer.echo(typer.style("✓ Validation successful!", typer.colors.GREEN))
    typer.echo(result["message"])

    for check_item in result.get("checks", []):
        typer.echo(f"  - {check_item['name']}: {check_item['filepath']}")


@app.command()
def run(
    phase: GatePhase = typer.Option(
        GatePhase.ITERATION_COMPLETE,
        "--phase",
        "-p",
        help="Quality-check execution phase.",
    ),
) -> None:
    """Execute all configured quality checks."""
    typer.echo("Running quality checks...")

    # Initialize gate runner service
    service = CheckGateRunner()

    # Execute all checks in the selected phase for detailed output.
    result = service.run_checks_for_phase(phase=phase)

    if result["success"]:
        typer.echo(typer.style("✓ All checks passed!", typer.colors.GREEN))
    else:
        typer.echo(typer.style("✗ Some checks failed!", typer.colors.RED))

    for index, check_result in enumerate(result.get("results", []), start=1):
        typer.echo(_format_check_entry(check_result, index))

    if result.get("message"):
        typer.echo(result["message"])

    raise typer.Exit(code=0 if result["success"] else 1)
