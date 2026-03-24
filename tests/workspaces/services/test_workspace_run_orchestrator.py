"""Tests for the workspace run orchestrator."""

from datetime import UTC, datetime

from engineeringagent.workspaces.models import (
    ExecutionTarget,
    RunHandle,
    RunRequest,
    RunStatus,
    WorkspaceSession,
    WorkspaceSpec,
    WorkspaceStatus,
)
from engineeringagent.workspaces.services.workspace_run_orchestrator import (
    WorkspaceRunOrchestrator,
)


class _FakeWorkspaceProvider:
    def __init__(self, workspace: WorkspaceSession) -> None:
        self.created_with: WorkspaceSpec | None = None
        self._workspace = workspace

    def create(self, spec: WorkspaceSpec) -> WorkspaceSession:
        self.created_with = spec
        return self._workspace

    def get(self, workspace_id: str) -> WorkspaceSession:
        assert workspace_id == self._workspace.id
        return self._workspace

    def list(self) -> list[WorkspaceSession]:
        return [self._workspace]

    def destroy(self, workspace_id: str) -> None:
        assert workspace_id == self._workspace.id


class _FakeWorkspaceRunner:
    def __init__(self, run: RunHandle) -> None:
        self.started_with: tuple[str, RunRequest] | None = None
        self._run = run

    def start_run(self, workspace_id: str, request: RunRequest) -> RunHandle:
        self.started_with = (workspace_id, request)
        return self._run

    def get_run(self, run_id: str) -> RunHandle:
        assert run_id == self._run.id
        return self._run

    def list_runs(self, workspace_id: str | None = None) -> list[RunHandle]:
        if workspace_id is None or workspace_id == self._run.workspace_id:
            return [self._run]
        return []

    def cancel_run(self, run_id: str) -> None:
        assert run_id == self._run.id


def test_orchestrator_creates_workspace_then_starts_run() -> None:
    """Orchestrator should compose provider and runner without extra logic."""
    workspace = WorkspaceSession(
        id="workspace-1",
        provider="git_worktree",
        status=WorkspaceStatus.READY,
        created_at=datetime.now(UTC),
        execution_target=ExecutionTarget(
            kind="local_path", location="/tmp/workspace-1"
        ),
    )
    run = RunHandle(
        id="run-1",
        workspace_id=workspace.id,
        status=RunStatus.SUCCEEDED,
        agent_kind="implementation",
    )
    provider = _FakeWorkspaceProvider(workspace)
    runner = _FakeWorkspaceRunner(run)
    orchestrator = WorkspaceRunOrchestrator(provider, runner)
    spec = WorkspaceSpec(
        provider="git_worktree",
        repo_path=".",
        base_branch="main",
        task_id="task-123",
    )
    request = RunRequest(agent_kind="implementation", context={})

    created_workspace, started_run = orchestrator.run_in_workspace(spec, request)

    assert created_workspace == workspace
    assert started_run == run
    assert provider.created_with == spec
    assert runner.started_with == (workspace.id, request)
