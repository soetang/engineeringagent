"""Tests for file-backed workspace registry."""

from datetime import UTC, datetime

from developer.workspaces.models import (
    ExecutionTarget,
    RunHandle,
    RunStatus,
    WorkspaceSession,
    WorkspaceStatus,
)
from developer.workspaces.services.file_registry import FileWorkspaceRegistry


def test_file_registry_saves_and_lists_workspaces_and_runs(tmp_path) -> None:
    """Registry should round-trip persisted workspace and run records."""
    registry = FileWorkspaceRegistry(tmp_path)
    workspace = WorkspaceSession(
        id="workspace-1",
        provider="git_worktree",
        status=WorkspaceStatus.READY,
        created_at=datetime.now(UTC),
        execution_target=ExecutionTarget(
            kind="local_path", location="/tmp/workspace-1"
        ),
        metadata={"branch_name": "developer/task/workspace-1"},
    )
    run = RunHandle(
        id="run-1",
        workspace_id=workspace.id,
        status=RunStatus.SUCCEEDED,
        agent_kind="implementation",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        latest_message="done",
        result_summary="iterations=1",
    )

    registry.save_workspace(workspace)
    registry.save_run(run)

    assert registry.get_workspace(workspace.id) == workspace
    assert registry.list_workspaces() == [workspace]
    assert registry.get_run(run.id) == run
    assert registry.list_runs() == [run]
    assert registry.list_runs(workspace_id=workspace.id) == [run]
    assert registry.list_runs(workspace_id="other") == []
