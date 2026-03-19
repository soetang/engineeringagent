"""Tests for application-owned workspace bridge adapters."""

from datetime import UTC, datetime
from typing import cast

import pytest

from developer.application.workspace_bridges import (
    DefaultWorkspaceRunnableAgentResolver,
    LocalExecutionAgentFactory,
    WorkspaceRunnableImplementationAgent,
)
from developer.agents.protocol import AgentProtocol
from developer.agents.select_agent_service import SelectAgentService
from developer.orchestrators.models import OrchestratorOutcome
from developer.workspaces.models import (
    ExecutionTarget,
    RunRequest,
    WorkspaceSession,
    WorkspaceStatus,
)


class _FakeAgentRunner:
    def __init__(
        self,
        profile: str | None = None,
        model: str | None = None,
        path: str | None = None,
    ) -> None:
        del profile, model, path

    def run_agent(self, prompt: str, output_format=None):
        del prompt, output_format
        return "done"


class _RecordingSelectAgentService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def select_agent(self, **kwargs) -> AgentProtocol:
        self.calls.append(kwargs)
        return cast(AgentProtocol, _FakeAgentRunner())


class _RecordingAgentFactory(LocalExecutionAgentFactory):
    def __init__(self, runner: AgentProtocol) -> None:
        self.runner = runner
        self.targets: list[ExecutionTarget] = []

    def for_execution_target(self, target: ExecutionTarget) -> AgentProtocol:
        self.targets.append(target)
        return self.runner


class _FakeImplementationAgent:
    def __init__(self, outcome: OrchestratorOutcome) -> None:
        self._outcome = outcome

    def run(self) -> OrchestratorOutcome:
        return self._outcome


def _workspace() -> WorkspaceSession:
    return WorkspaceSession(
        id="workspace-1",
        provider="git_worktree",
        status=WorkspaceStatus.READY,
        created_at=datetime.now(UTC),
        execution_target=ExecutionTarget(kind="local_path", location="/tmp/workspace"),
    )


def _patch_implementation_agent(monkeypatch, outcome: OrchestratorOutcome) -> None:
    monkeypatch.setattr(
        "developer.application.workspace_bridges.build_implementation_agent",
        lambda agent_runner: _FakeImplementationAgent(outcome),
    )


def test_local_execution_agent_factory_does_not_pass_workspace_path() -> None:
    """Local-path bridge selection should still rely on ambient cwd."""
    select_agent_service = _RecordingSelectAgentService()
    factory = LocalExecutionAgentFactory(
        select_agent_service=cast(SelectAgentService, select_agent_service)
    )

    runner = factory.for_execution_target(
        ExecutionTarget(kind="local_path", location="/tmp/workspace")
    )

    assert isinstance(runner, _FakeAgentRunner)
    assert select_agent_service.calls == [{}]


def test_workspace_runnable_implementation_agent_maps_success(monkeypatch) -> None:
    """Bridge should convert successful orchestrator outcomes into workspace results."""
    workspace = _workspace()
    runner = _fake_agent_runner()
    agent_factory = _RecordingAgentFactory(runner)
    _patch_implementation_agent(
        monkeypatch,
        OrchestratorOutcome(status="success", iterations=2),
    )

    result = WorkspaceRunnableImplementationAgent(agent_factory=agent_factory).run(
        request=RunRequest(agent_kind="implementation", context={}),
        workspace=workspace,
    )

    assert result.status == "succeeded"
    assert result.message == "Implementation run succeeded after 2 iterations"
    assert result.summary == "iterations=2"
    assert agent_factory.targets == [workspace.execution_target]


def test_workspace_runnable_implementation_agent_maps_failed_feedback(
    monkeypatch,
) -> None:
    """Bridge should preserve failure feedback in workspace results."""
    _patch_implementation_agent(
        monkeypatch,
        OrchestratorOutcome(
            status="failed",
            iterations=3,
            feedback="ruff check failed",
        ),
    )

    result = WorkspaceRunnableImplementationAgent(
        agent_factory=_RecordingAgentFactory(_fake_agent_runner())
    ).run(
        request=RunRequest(agent_kind="implementation", context={}),
        workspace=_workspace(),
    )

    assert result.status == "failed"
    assert (
        result.message
        == "Implementation run failed after 3 iterations: ruff check failed"
    )
    assert result.summary == "iterations=3"


def test_default_workspace_runnable_agent_resolver_supports_implementation() -> None:
    """Resolver should return the built-in implementation bridge."""
    resolved = DefaultWorkspaceRunnableAgentResolver().resolve("implementation")

    assert isinstance(resolved, WorkspaceRunnableImplementationAgent)


def test_default_workspace_runnable_agent_resolver_rejects_unknown_kind() -> None:
    """Resolver should reject unsupported workspace agent kinds."""
    with pytest.raises(ValueError, match="Unsupported agent kind: unknown"):
        DefaultWorkspaceRunnableAgentResolver().resolve("unknown")


def _fake_agent_runner() -> AgentProtocol:
    return cast(AgentProtocol, _FakeAgentRunner())
