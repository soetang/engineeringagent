"""Application service for markdown task plan validation."""

from pathlib import Path

from developer.tasks.models import PlanValidationResult
from developer.tasks.select_service import TaskSelectionService


def validate_plan(
    task_input: str, *, base_path: Path | None = None
) -> PlanValidationResult:
    """Validate one user-supplied plan path through the task selection service."""
    return TaskSelectionService().validate_plan(task_input, base_path=base_path)
