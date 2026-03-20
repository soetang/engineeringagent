"""Protocol interfaces for task resolution and execution."""

from typing import Protocol

from developer.orchestrators.models import CompletionResult

from .models import TaskIdentity


class ImplementationTask(Protocol):
    """Task contract used by the implementation orchestrator."""

    @property
    def identity(self) -> TaskIdentity:
        """Return the stable task identity."""
        ...

    def is_complete(self) -> CompletionResult:
        """Return whether the task is currently complete."""
        ...

    def get_branch_name(self) -> str:
        """Return the stable publication branch name for this task."""
        ...
