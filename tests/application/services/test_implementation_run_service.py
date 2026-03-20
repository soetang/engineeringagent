"""Tests for the implementation run application service."""

from developer.application.services.implementation_run_service import (
    run_implementation,
)
from developer.orchestrators.models import OrchestratorOutcome
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
        lambda config_service, task: task.get_branch_name(),
    )

    result = run_implementation(task_name="add-version-control")

    assert result.exit_code == 0
    assert "task=add-version-control" in result.message
    assert "commits=1" in result.message
    assert "branch=add-version-control" in result.message
