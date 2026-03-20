"""Simple implementation task model."""

from developer.orchestrators.models import CompletionResult


class SimpleImplementationTask:
    """Mock-friendly implementation task used for v1 task behavior."""

    def __init__(self, task_input: str, task_path: str | None = None) -> None:
        """Create a task whose branch derives directly from the task name."""
        normalized_input = task_input.strip()
        if not normalized_input:
            raise ValueError("Task input must not be empty")
        self._task_name = normalized_input
        self._task_path = task_path

    @property
    def task_name(self) -> str:
        """Return the current task name."""
        return self._task_name

    @property
    def task_path(self) -> str | None:
        """Return the current task path when present."""
        return self._task_path

    def is_complete(self) -> CompletionResult:
        """Always report completion for the current mock task flow."""
        return CompletionResult.COMPLETE

    def get_branch_name(self) -> str:
        """Return the current task name as the publication branch for now."""
        return self._task_name
