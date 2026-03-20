"""Protocol interfaces for task resolution and execution."""

from typing import Protocol

from developer.orchestrators.models import CompletionResult


class ImplementationTask(Protocol):
    """Task contract used by the implementation orchestrator."""

    @property
    def task_id(self) -> str:
        """Return the stable task identity."""
        ...

    @property
    def task_name(self) -> str:
        """Return the current task name."""
        ...

    @property
    def task_path(self) -> str | None:
        """Return the current task path when present."""
        ...

    def is_complete(self) -> CompletionResult:
        """Return whether the task is currently complete."""
        ...

    def get_branch_name(self) -> str:
        """Return the stable publication branch name for this task."""
        ...
