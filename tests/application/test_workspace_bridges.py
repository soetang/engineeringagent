"""Tests for application-owned workspace bridge adapters."""

from datetime import UTC, datetime
from typing import cast

import pytest

from engineeringagent.application.workspace_bridges import (
    DefaultWorkspaceRunnableAgentResolver,
    LocalExecutionAgentFactory,
    WorkspaceRunnableImplementationAgent,
)
from engineeringagent.agent_backends.protocol import AgentBackendProtocol
from engineeringagent.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from engineeringagent.orchestrators.loop.models import OrchestratorOutcome
from engineeringagent.workspaces.models import (
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


class _RecordingSelectAgentBackendService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def select_agent(self, **kwargs) -> AgentBackendProtocol:
        self.calls.append(kwargs)
        return cast(AgentBackendProtocol, _FakeAgentRunner())


class _RecordingAgentFactory(LocalExecutionAgentFactory):
    def __init__(self, runner: AgentBackendProtocol) -> None:
        self.runner = runner
        self.targets: list[ExecutionTarget] = []

    def for_execution_target(self, target: ExecutionTarget) -> AgentBackendProtocol:
        self.targets.append(target)
        return self.runner


class _RecordingObserver:
    def __init__(self) -> None:
        self.validated_contexts = []

    def validate(self, context) -> None:
        self.validated_contexts.append(context)

    def on_iteration_passed(self, attempt, context, agent_result):
        del attempt, context, agent_result
        return None

    def on_run_succeeded(self, context):
        del context
        return None

    def on_run_failed(self, context, feedback):
        del context, feedback
        return None


class _FakeImplementationAgent:
    def __init__(self, outcome: OrchestratorOutcome) -> None:
        self._outcome = outcome

    def run(self) -> OrchestratorOutcome:
        return self._outcome


class _ResolvedTask:
    def __init__(self, task_id: str, task_name: str, task_path: str | None) -> None:
        self._task_id = task_id
        self._task_name = task_name
        self._task_path = task_path

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def task_name(self) -> str:
        return self._task_name

    @property
    def task_path(self) -> str | None:
        return self._task_path

    def is_complete(self):
        raise NotImplementedError

    def get_branch_name(self) -> str:
        return self._task_id


def _workspace() -> WorkspaceSession:
    return WorkspaceSession(
        id="workspace-1",
        provider="git_worktree",
        status=WorkspaceStatus.READY,
        created_at=datetime.now(UTC),
        execution_target=ExecutionTarget(
            kind="local_path",
            location="/tmp/workspace",
            metadata={"repo_path": "/tmp/repo"},
        ),
        metadata={
            "workspace_branch_name": "engineeringagent/ship-it/ws-123",
            "task_branch_name": "ship-it",
            "base_branch": "main",
            "remote_name": "origin",
        },
    )


def test_local_execution_agent_factory_does_not_pass_workspace_path() -> None:
    """Local-path bridge selection should still rely on ambient cwd."""
    select_agent_backend_service = _RecordingSelectAgentBackendService()
    factory = LocalExecutionAgentFactory(
        select_agent_backend_service=cast(
            SelectAgentBackendService, select_agent_backend_service
        )
    )

    runner = factory.for_execution_target(
        ExecutionTarget(kind="local_path", location="/tmp/workspace")
    )

    assert isinstance(runner, _FakeAgentRunner)
    assert select_agent_backend_service.calls == [{}]


def test_workspace_runnable_implementation_agent_maps_success(monkeypatch) -> None:
    """Bridge should re-resolve the task and map successful outcomes."""
    workspace = _workspace()
    runner = cast(AgentBackendProtocol, _FakeAgentRunner())
    agent_factory = _RecordingAgentFactory(runner)
    observer = _RecordingObserver()
    resolved_tasks: list[tuple[str, str]] = []
    agent_calls: list[int | None] = []

    def fake_resolve(self, task_input, base_path=None):
        del self
        resolved_tasks.append((task_input, str(base_path)))
        return _ResolvedTask(
            "ship-it", "Ship it", "/tmp/workspace/docs/plans/ship-it.md"
        )

    def fake_build_implementation_agent(
        agent_runner, task, observer=None, context=None, max_iterations=None
    ):
        del agent_runner, task, observer, context
        agent_calls.append(max_iterations)
        return _FakeImplementationAgent(
            OrchestratorOutcome(status="success", iterations=2)
        )

    monkeypatch.setattr(
        "engineeringagent.application.workspace_bridges.TaskSelectionService.resolve",
        fake_resolve,
    )
    monkeypatch.setattr(
        "engineeringagent.application.workspace_bridges.build_implementation_agent",
        fake_build_implementation_agent,
    )

    result = WorkspaceRunnableImplementationAgent(
        agent_factory=agent_factory,
        observer=observer,
    ).run(
        request=RunRequest(
            agent_kind="implementation",
            context={
                "task_input": "docs/plans/ship-it.md",
                "run_id": "run-1",
                "max_iterations": 20,
            },
        ),
        workspace=workspace,
    )

    assert result.status == "succeeded"
    assert result.message == "Implementation run succeeded after 2 iterations"
    assert agent_factory.targets == [workspace.execution_target]
    assert resolved_tasks == [("docs/plans/ship-it.md", "/tmp/workspace")]
    assert agent_calls == [20]
    assert observer.validated_contexts[0].repo_path == "/tmp/repo"
    assert observer.validated_contexts[0].workspace_path == "/tmp/workspace"
    assert (
        observer.validated_contexts[0].task_path
        == "/tmp/workspace/docs/plans/ship-it.md"
    )


def test_workspace_runnable_implementation_agent_maps_failed_feedback(
    monkeypatch,
) -> None:
    """Bridge should preserve failure feedback in workspace results."""

    def fake_build_implementation_agent(
        agent_runner, task, observer=None, context=None, max_iterations=None
    ):
        del agent_runner, task, observer, context, max_iterations
        return _FakeImplementationAgent(
            OrchestratorOutcome(
                status="failed",
                iterations=3,
                feedback="ruff check failed",
            )
        )

    monkeypatch.setattr(
        "engineeringagent.application.workspace_bridges.TaskSelectionService.resolve",
        lambda self, task_input, base_path=None: _ResolvedTask(
            "ship-it", "Ship it", "/tmp/workspace/docs/plans/ship-it.md"
        ),
    )
    monkeypatch.setattr(
        "engineeringagent.application.workspace_bridges.build_implementation_agent",
        fake_build_implementation_agent,
    )

    result = WorkspaceRunnableImplementationAgent(
        agent_factory=_RecordingAgentFactory(
            cast(AgentBackendProtocol, _FakeAgentRunner())
        )
    ).run(
        request=RunRequest(
            agent_kind="implementation", context={"task_input": "docs/plans/ship-it.md"}
        ),
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
