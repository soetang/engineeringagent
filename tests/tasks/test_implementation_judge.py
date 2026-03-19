"""Tests for the implementation completion judge."""

from developer.orchestrators.models import CompletionResult
from developer.tasks.implementation_judge import ImplementationJudge


def test_implementation_judge_always_reports_complete() -> None:
    """The stub implementation judge should always report completion."""
    judge = ImplementationJudge()

    assert judge.is_complete() == CompletionResult.COMPLETE
