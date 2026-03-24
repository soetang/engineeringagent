"""Application service for repository onboarding."""

from pathlib import Path

from developer.scaffolding.models import InitRequest, InitResult
from developer.scaffolding.service import ScaffoldingService


def initialize_repository(
    request: InitRequest,
    *,
    base_path: Path | None = None,
) -> InitResult:
    """Run the repository onboarding workflow."""
    return ScaffoldingService().run(request, base_path=base_path or Path.cwd())
