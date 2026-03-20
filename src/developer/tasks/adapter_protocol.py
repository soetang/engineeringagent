"""Protocol boundary for pluggable task adapters."""

from typing import Protocol

from developer.tasks.models import PlanValidationResult
from developer.tasks.protocol import ImplementationTask


class TaskAdapter(Protocol):
    """Adapter that resolves one family of task inputs."""

    def can_resolve(self, task_input: str) -> bool:
        """Return whether this adapter can resolve the task input."""
        ...

    def resolve(self, task_input: str) -> ImplementationTask:
        """Resolve one task input into a concrete task object."""
        ...

    def validate(self, task_input: str) -> PlanValidationResult:
        """Validate one task input without executing it."""
        ...
