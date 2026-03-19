"""Tests for the local process workspace runner."""

from datetime import UTC, datetime

import pytest

from developer.orchestrators.workspace_protocols import WorkspaceRunnableAgent
from developer.workspaces.adapters.local_process_runner import (
    LocalProcessWorkspaceRunner,
)
from developer.workspaces.models import (
    ExecutionTarget,
    RunRequest,
    RunStatus,
    WorkspaceRunnableResult,
    WorkspaceSession,
    WorkspaceStatus,
)
from developer.workspaces.services.file_registry import FileWorkspaceRegistry


class _SuccessfulAgent(WorkspaceRunnableAgent):
    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        del request, workspace
        return WorkspaceRunnableResult(
            status="succeeded",
            message="updated files",
            summary="updated files",
        )


class _UnsuccessfulAgent(WorkspaceRunnableAgent):
    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        del request, workspace
        return WorkspaceRunnableResult(
            status="failed",
            message="last failing feedback",
            summary="iterations=3",
        )


class _FailingAgent(WorkspaceRunnableAgent):
    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        del request, workspace
        raise RuntimeError("boom")


class _StaticResolver:
    def __init__(self, agent: WorkspaceRunnableAgent) -> None:
        self._agent = agent

    def resolve(self, agent_kind: str) -> WorkspaceRunnableAgent:
        del agent_kind
        return self._agent


def _workspace_session() -> WorkspaceSession:
    return WorkspaceSession(
        id="workspace-1",
        provider="git_worktree",
        status=WorkspaceStatus.READY,
        created_at=datetime.now(UTC),
        execution_target=ExecutionTarget(
            kind="local_path", location="/tmp/workspace-1"
        ),
    )


def test_runner_marks_run_succeeded(tmp_path) -> None:
    """Runner should persist pending, running, and succeeded transitions."""
    registry = FileWorkspaceRegistry(tmp_path)
    workspace = _workspace_session()
    registry.save_workspace(workspace)
    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=_StaticResolver(_SuccessfulAgent()),
    )

    run = runner.start_run(
        workspace_id=workspace.id,
        request=RunRequest(agent_kind="implementation", context={}),
    )

    persisted_run = registry.get_run(run.id)
    assert run.status is RunStatus.SUCCEEDED
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.result_summary == "updated files"
    assert persisted_run == run


def test_runner_marks_run_failed_without_raising_for_unsuccessful_result(
    tmp_path,
) -> None:
    """Runner should persist a failed terminal state for unsuccessful run results."""
    registry = FileWorkspaceRegistry(tmp_path)
    workspace = _workspace_session()
    registry.save_workspace(workspace)
    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=_StaticResolver(_UnsuccessfulAgent()),
    )

    run = runner.start_run(
        workspace_id=workspace.id,
        request=RunRequest(agent_kind="implementation", context={}),
    )

    assert run.status is RunStatus.FAILED
    assert run.latest_message == "last failing feedback"
    assert run.result_summary == "iterations=3"


def test_runner_marks_run_failed_and_persists_failure(tmp_path) -> None:
    """Runner should persist a failed terminal state when a workflow raises."""
    registry = FileWorkspaceRegistry(tmp_path)
    workspace = _workspace_session()
    registry.save_workspace(workspace)
    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=_StaticResolver(_FailingAgent()),
    )

    with pytest.raises(RuntimeError, match="boom"):
        runner.start_run(
            workspace_id=workspace.id,
            request=RunRequest(agent_kind="implementation", context={}),
        )

    persisted_run = registry.list_runs()[0]
    assert persisted_run.status is RunStatus.FAILED
    assert persisted_run.started_at is not None
    assert persisted_run.finished_at is not None
    assert persisted_run.latest_message == "boom"
