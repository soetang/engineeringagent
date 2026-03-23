"""Application service for repository onboarding."""

from pathlib import Path

from developer.application.models import InitRequest, InitResult
from developer.scaffolding.models import InitRequest as ScaffoldingInitRequest
from developer.scaffolding.service import ScaffoldingService


def initialize_repository(
    request: InitRequest,
    *,
    base_path: Path | None = None,
) -> InitResult:
    """Run the repository onboarding workflow."""
    result = ScaffoldingService().run(
        ScaffoldingInitRequest(**request.model_dump()),
        base_path=base_path or Path.cwd(),
    )
    return InitResult.model_validate(result.model_dump())
