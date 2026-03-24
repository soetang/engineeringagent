"""Errors raised by task resolution and validation."""


class TaskError(RuntimeError):
    """Base error for task subsystem failures."""


class TaskPlanLoadError(TaskError):
    """Raised when a task plan cannot be read or parsed."""


class TaskPlanValidationError(TaskError):
    """Raised when a task plan is semantically invalid."""
