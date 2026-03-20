"""Tests for the implementation run application service."""

from pathlib import Path

from developer.application.services.implementation_run_service import (
    _resolve_task_branch,
    _resolve_workspace_start_point,
    run_implementation,
)
from developer.orchestrators.models import OrchestratorOutcome
from developer.tasks.implementation_task import SimpleImplementationTask
from developer.tasks.models import TaskPublicationState
from developer.workspaces.models import RunHandle, RunStatus


class _FakeImplementationAgent:
    def __init__(self, outcome: OrchestratorOutcome) -> None:
        self._outcome = outcome

    def run(self) -> OrchestratorOutcome:
        return self._outcome


class _FakeWorkspaceOrchestrator:
    def run_in_workspace(self, workspace_spec, request):
        assert workspace_spec.metadata["task_branch_name"] == "add-version-control"
        assert request.context["task_name"] == "add-version-control"

        class _Workspace:
            id = "workspace-1"

        return _Workspace(), RunHandle(
            id="run-1",
            workspace_id="workspace-1",
            status=RunStatus.SUCCEEDED,
            agent_kind="implementation",
            latest_message="Implementation run succeeded after 1 iterations",
            metadata={
                "commit_shas": ["abc123"],
                "task_branch_name": "add-version-control",
            },
        )


def test_run_implementation_returns_failure_feedback(monkeypatch) -> None:
    """Direct runs should surface the last failure feedback."""
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._workspace_mode_enabled",
        lambda config_service: False,
    )
    monkeypatch.setattr(
        "developer.agent_backends.select_agent_backend_service.SelectAgentBackendService.select_agent",
        lambda self: object(),
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.build_implementation_agent",
        lambda agent_runner, task: _FakeImplementationAgent(
            OrchestratorOutcome(
                status="failed",
                iterations=3,
                feedback="ruff check failed",
            )
        ),
    )

    result = run_implementation(task_name="add-version-control")

    assert result.exit_code == 1
    assert result.message == "Implementation run failed: ruff check failed"


def test_workspace_run_formats_task_and_commit_count(monkeypatch) -> None:
    """Workspace runs should include task and commit metadata in the final message."""
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._workspace_mode_enabled",
        lambda config_service: True,
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.build_workspace_orchestrator",
        lambda config_service: _FakeWorkspaceOrchestrator(),
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._resolve_current_branch",
        lambda repo_path: "main",
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._resolve_task_branch",
        lambda repo_path, task, publication: task.get_branch_name(),
    )

    result = run_implementation(task_name="add-version-control")

    assert result.exit_code == 0
    assert "task=add-version-control" in result.message
    assert "commits=1" in result.message
    assert "branch=add-version-control" in result.message


def test_resolve_task_branch_reuses_existing_publication() -> None:
    """Existing publication state should own future branch reuse."""
    task = SimpleImplementationTask("add-version-control")
    publication = TaskPublicationState(
        task_name="add-version-control",
        task_path=None,
        branch_name="published-branch",
        base_branch="main",
        status="created",
    )

    branch = _resolve_task_branch(Path("."), task, publication)

    assert branch == "published-branch"


def test_resolve_task_branch_adds_suffix_when_candidate_exists(monkeypatch) -> None:
    """New tasks should avoid colliding with existing publication branches."""
    task = SimpleImplementationTask("add-version-control")
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._branch_exists",
        lambda repo_path, branch_name, remote_name: True,
    )

    branch = _resolve_task_branch(Path("."), task, publication=None)

    assert branch.startswith("add-version-control-")


def test_resolve_workspace_start_point_prefers_publication_branch() -> None:
    """Follow-up runs should start from the publication branch when present."""
    publication = TaskPublicationState(
        task_name="add-version-control",
        task_path=None,
        branch_name="published-branch",
        base_branch="main",
        status="created",
    )

    start_point = _resolve_workspace_start_point(
        publication=publication,
        base_branch="main",
    )

    assert start_point == "published-branch"
