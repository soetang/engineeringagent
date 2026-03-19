"""Implementation completion judge."""

from developer.orchestrators.models import CompletionResult


class ImplementationJudge:
    """Stub judge used while the implementation loop is being wired."""

    def is_complete(self) -> CompletionResult:
        """Always report completion for the current mock flow."""
        return CompletionResult.COMPLETE
