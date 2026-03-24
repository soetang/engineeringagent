"""Tests for the local process workspace runner."""

from datetime import UTC, datetime

import pytest

from engineeringagent.workspaces.adapters.local_process_runner import (
    LocalProcessWorkspaceRunner,
)
from engineeringagent.workspaces.models import (
    ExecutionTarget,
    RunRequest,
    RunStatus,
    WorkspaceRunnableResult,
    WorkspaceSession,
    WorkspaceStatus,
)
from engineeringagent.workspaces.protocols import WorkspaceRunnableAgent
from engineeringagent.workspaces.services.file_registry import FileWorkspaceRegistry


class _ResolvedAgent(WorkspaceRunnableAgent):
    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        del request, workspace
        raise AssertionError("execution adapter should call the agent in these tests")


class _StaticAgentResolver:
    def __init__(self, agent: WorkspaceRunnableAgent) -> None:
        self._agent = agent
        self.agent_kinds: list[str] = []

    def resolve(self, agent_kind: str) -> WorkspaceRunnableAgent:
        self.agent_kinds.append(agent_kind)
        return self._agent


class _RecordingExecutionAdapter:
    def __init__(
        self,
        result: WorkspaceRunnableResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[
            tuple[WorkspaceSession, RunRequest, WorkspaceRunnableAgent]
        ] = []
        self._result = result
        self._error = error

    def run(
        self,
        workspace: WorkspaceSession,
        request: RunRequest,
        agent: WorkspaceRunnableAgent,
    ) -> WorkspaceRunnableResult:
        self.calls.append((workspace, request, agent))
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _StaticExecutionAdapterResolver:
    def __init__(self, adapter: _RecordingExecutionAdapter) -> None:
        self._adapter = adapter
        self.targets: list[ExecutionTarget] = []

    def resolve(self, target: ExecutionTarget) -> _RecordingExecutionAdapter:
        self.targets.append(target)
        return self._adapter


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


def _build_runner(
    tmp_path,
    *,
    execution_adapter: _RecordingExecutionAdapter,
    agent: WorkspaceRunnableAgent | None = None,
) -> tuple[
    FileWorkspaceRegistry,
    WorkspaceSession,
    _StaticAgentResolver,
    _StaticExecutionAdapterResolver,
    LocalProcessWorkspaceRunner,
]:
    registry = FileWorkspaceRegistry(tmp_path)
    workspace = _workspace_session()
    registry.save_workspace(workspace)
    resolved_agent = agent or _ResolvedAgent()
    agent_resolver = _StaticAgentResolver(resolved_agent)
    execution_adapter_resolver = _StaticExecutionAdapterResolver(execution_adapter)
    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=agent_resolver,
        execution_adapter_resolver=execution_adapter_resolver,
    )
    return (
        registry,
        workspace,
        agent_resolver,
        execution_adapter_resolver,
        runner,
    )


def test_runner_marks_run_succeeded(tmp_path) -> None:
    """Runner should persist pending, running, and succeeded transitions."""
    agent = _ResolvedAgent()
    execution_adapter = _RecordingExecutionAdapter(
        result=WorkspaceRunnableResult(
            status="succeeded",
            message="updated files",
            summary="updated files",
        )
    )
    registry, workspace, agent_resolver, execution_adapter_resolver, runner = (
        _build_runner(
            tmp_path,
            agent=agent,
            execution_adapter=execution_adapter,
        )
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
    assert agent_resolver.agent_kinds == ["implementation"]
    assert execution_adapter_resolver.targets == [workspace.execution_target]
    assert execution_adapter.calls[0][0] == workspace
    assert execution_adapter.calls[0][2] is agent
    assert execution_adapter.calls[0][1].agent_kind == "implementation"
    assert execution_adapter.calls[0][1].context["run_id"] == run.id


def test_runner_marks_run_failed_without_raising_for_unsuccessful_result(
    tmp_path,
) -> None:
    """Runner should persist a failed terminal state for unsuccessful run results."""
    _, workspace, _, _, runner = _build_runner(
        tmp_path,
        execution_adapter=_RecordingExecutionAdapter(
            result=WorkspaceRunnableResult(
                status="failed",
                message="last failing feedback",
                summary="iterations=3",
            )
        ),
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
    registry, workspace, _, _, runner = _build_runner(
        tmp_path,
        execution_adapter=_RecordingExecutionAdapter(error=RuntimeError("boom")),
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
