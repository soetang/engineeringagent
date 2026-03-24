"""Application services for quality-check commands."""

from typing import Any

from engineeringagent.orchestrators.loop.models import GatePhase
from engineeringagent.quality.services import CheckGateRunner
from engineeringagent.quality.services.validation_service import ValidationService


def validate_checks() -> dict[str, Any]:
    """Validate the configured quality checks."""
    return ValidationService().validate_checks_yaml()


def run_checks(phase: str = GatePhase.ITERATION_COMPLETE.value) -> dict[str, Any]:
    """Run the configured quality checks for the requested phase."""
    return CheckGateRunner().run_checks_for_phase(phase=GatePhase(phase))
