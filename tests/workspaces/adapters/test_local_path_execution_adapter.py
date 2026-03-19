"""Tests for the local-path workspace execution adapter."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from developer.workspaces.adapters.local_path_execution_adapter import (
    LocalPathWorkspaceExecutionAdapter,
)
from developer.workspaces.models import (
    ExecutionTarget,
    RunRequest,
    WorkspaceRunnableResult,
    WorkspaceSession,
    WorkspaceStatus,
)
from developer.workspaces.protocols import WorkspaceRunnableAgent


class _RecordingAgent(WorkspaceRunnableAgent):
    def __init__(self, result: WorkspaceRunnableResult) -> None:
        self.cwd_during_run: Path | None = None
        self.calls: list[tuple[RunRequest, WorkspaceSession]] = []
        self._result = result

    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        self.cwd_during_run = Path.cwd()
        self.calls.append((request, workspace))
        return self._result


class _FailingAgent(WorkspaceRunnableAgent):
    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        del request, workspace
        raise RuntimeError("boom")


def _workspace(workspace_root: Path) -> WorkspaceSession:
    return WorkspaceSession(
        id="workspace-1",
        provider="git_worktree",
        status=WorkspaceStatus.READY,
        created_at=datetime.now(UTC),
        execution_target=ExecutionTarget(
            kind="local_path", location=str(workspace_root)
        ),
    )


def test_local_path_adapter_runs_agent_inside_workspace_directory(tmp_path) -> None:
    """Adapter should run the agent with the workspace path as cwd."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    workspace = _workspace(workspace_root)
    request = RunRequest(agent_kind="implementation", context={})
    result = WorkspaceRunnableResult(
        status="succeeded",
        message="done",
        summary="iterations=1",
    )
    agent = _RecordingAgent(result)

    returned_result = LocalPathWorkspaceExecutionAdapter().run(
        workspace=workspace,
        request=request,
        agent=agent,
    )

    assert returned_result == result
    assert agent.cwd_during_run == workspace_root
    assert agent.calls == [(request, workspace)]


def test_local_path_adapter_restores_previous_directory_after_success(tmp_path) -> None:
    """Adapter should restore cwd after a successful run."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    previous_cwd = Path.cwd()

    LocalPathWorkspaceExecutionAdapter().run(
        workspace=_workspace(workspace_root),
        request=RunRequest(agent_kind="implementation", context={}),
        agent=_RecordingAgent(
            WorkspaceRunnableResult(status="succeeded", message="done")
        ),
    )

    assert Path.cwd() == previous_cwd


def test_local_path_adapter_restores_previous_directory_after_failure(tmp_path) -> None:
    """Adapter should restore cwd even when the agent raises."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    previous_cwd = Path.cwd()

    with pytest.raises(RuntimeError, match="boom"):
        LocalPathWorkspaceExecutionAdapter().run(
            workspace=_workspace(workspace_root),
            request=RunRequest(agent_kind="implementation", context={}),
            agent=_FailingAgent(),
        )

    assert Path.cwd() == previous_cwd


def test_local_path_adapter_rejects_non_local_target(tmp_path) -> None:
    """Adapter should reject execution targets it does not support."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    invalid_target = ExecutionTarget.model_construct(
        kind=cast(Any, "container"),
        location=str(workspace_root),
        metadata={},
    )
    workspace = _workspace(workspace_root).model_copy(
        update={"execution_target": invalid_target}
    )

    with pytest.raises(
        ValueError,
        match="LocalPathWorkspaceExecutionAdapter requires local_path target",
    ):
        LocalPathWorkspaceExecutionAdapter().run(
            workspace=workspace,
            request=RunRequest(agent_kind="implementation", context={}),
            agent=_RecordingAgent(
                WorkspaceRunnableResult(status="succeeded", message="done")
            ),
        )
