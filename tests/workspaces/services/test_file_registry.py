"""Tests for file-backed workspace registry."""

from datetime import UTC, datetime

from engineeringagent.tasks.models import TaskPublicationState
from engineeringagent.workspaces.models import (
    ExecutionTarget,
    RunHandle,
    RunStatus,
    WorkspaceSession,
    WorkspaceStatus,
)
from engineeringagent.workspaces.services.file_registry import FileWorkspaceRegistry


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
        metadata={"workspace_branch_name": "engineeringagent/task/ws-workspace-1"},
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


def test_file_registry_saves_task_publication_state(tmp_path) -> None:
    """Registry should round-trip publication state by task identity."""
    registry = FileWorkspaceRegistry(tmp_path)
    publication = TaskPublicationState(
        task_name="add-version-control",
        task_path=None,
        branch_name="add-version-control",
        base_branch="main",
        pr_url="https://example.com/pr/1",
        pr_number="1",
        status="created",
    )

    registry.save_task_publication(publication)

    assert registry.get_task_publication("add-version-control") == publication
    assert (
        registry.get_task_publication_branch("add-version-control")
        == "add-version-control"
    )
