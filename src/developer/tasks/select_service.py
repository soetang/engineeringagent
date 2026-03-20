"""Select and execute task adapters for implementation flows."""

from pathlib import Path

from developer.tasks.adapter_protocol import TaskAdapter
from developer.tasks.adapters.markdown_plan_adapter import MarkdownPlanAdapter
from developer.tasks.errors import TaskPlanLoadError
from developer.tasks.models import PlanValidationError, PlanValidationResult
from developer.tasks.protocol import ImplementationTask


class TaskSelectionService:
    """Resolve and validate task inputs through configured adapters."""

    def __init__(self, adapters: list[TaskAdapter] | None = None) -> None:
        """Store the adapter list in resolution order."""
        self._adapters = adapters or [MarkdownPlanAdapter()]

    def resolve(
        self,
        task_input: str,
        *,
        base_path: Path | None = None,
    ) -> ImplementationTask:
        """Resolve one user task input into a concrete task object."""
        normalized, adapter = self._resolve_adapter_input(
            task_input, base_path=base_path
        )
        return adapter.resolve(normalized)

    def validate_plan(
        self,
        task_input: str,
        *,
        base_path: Path | None = None,
    ) -> PlanValidationResult:
        """Validate one user task input for the CLI."""
        try:
            normalized, adapter = self._resolve_adapter_input(
                task_input, base_path=base_path
            )
            return adapter.validate(normalized)
        except TaskPlanLoadError as exc:
            return PlanValidationResult(
                valid=False,
                errors=[
                    PlanValidationError(location="path", message=str(exc)),
                ],
            )

    def _resolve_adapter_input(
        self,
        task_input: str,
        *,
        base_path: Path | None,
    ) -> tuple[str, TaskAdapter]:
        """Normalize one task input and select the adapter that handles it."""
        normalized = self._normalize_task_input(task_input, base_path=base_path)
        return normalized, self._select_adapter(normalized)

    def _select_adapter(self, task_input: str) -> TaskAdapter:
        """Return the first adapter that can resolve the input."""
        for adapter in self._adapters:
            if adapter.can_resolve(task_input):
                return adapter
        raise TaskPlanLoadError(f"Unsupported task input: {task_input}")

    def _normalize_task_input(self, task_input: str, *, base_path: Path | None) -> str:
        """Normalize a user-facing path input into a filesystem path string."""
        normalized = task_input.strip()
        if not normalized:
            raise TaskPlanLoadError("Task input must not be empty")
        if normalized.startswith("@"):
            normalized = normalized[1:]
        candidate = Path(normalized).expanduser()
        if not candidate.is_absolute():
            candidate = (base_path or Path.cwd()) / candidate
        return str(candidate.resolve())
