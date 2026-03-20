"""Backward-compatible implementation completion judge."""

from developer.tasks.implementation_task import SimpleImplementationTask


class ImplementationJudge(SimpleImplementationTask):
    """Legacy wrapper around the simple implementation task model."""

    def __init__(self) -> None:
        """Create the legacy stub task instance."""
        super().__init__("implementation")
