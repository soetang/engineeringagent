"""Tests for the implementation task stubs."""

from developer.orchestrators.models import CompletionResult
from developer.tasks.implementation_judge import ImplementationJudge
from developer.tasks.implementation_task import SimpleImplementationTask


def test_implementation_judge_always_reports_complete() -> None:
    """The stub implementation judge should always report completion."""
    judge = ImplementationJudge()

    assert judge.is_complete() == CompletionResult.COMPLETE


def test_simple_implementation_task_uses_task_name_for_branch_name() -> None:
    """The simple task should reuse the task name as its branch name."""
    task = SimpleImplementationTask("add-version-control")

    assert task.task_name == "add-version-control"
    assert task.get_branch_name() == "add-version-control"
