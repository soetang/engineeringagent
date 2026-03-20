"""Simple implementation task model."""

from developer.orchestrators.models import CompletionResult

from .models import TaskIdentity


class SimpleImplementationTask:
    """Mock-friendly implementation task used for v1 task identity."""

    def __init__(self, task_input: str, task_path: str | None = None) -> None:
        """Create a task whose identity and branch derive from one input."""
        normalized_input = task_input.strip()
        if not normalized_input:
            raise ValueError("Task input must not be empty")
        self._identity = TaskIdentity(name=normalized_input, path=task_path)

    @property
    def identity(self) -> TaskIdentity:
        """Return the stable task identity."""
        return self._identity

    def is_complete(self) -> CompletionResult:
        """Always report completion for the current mock task flow."""
        return CompletionResult.COMPLETE

    def get_branch_name(self) -> str:
        """Return a stable publication branch name derived from task identity."""
        return self._identity.name
