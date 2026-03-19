"""Tests for application-layer workspace runtime helpers."""

from developer.application.workspace_runtime import LocalExecutionAgentFactory
from developer.workspaces.models import ExecutionTarget


class _FakeAgentRunner:
    pass


class _RecordingSelectAgentService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def select_agent(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeAgentRunner()


def test_local_execution_agent_factory_does_not_pass_workspace_path() -> None:
    """Workspace-backed local runs should rely on cwd, not adapter path."""
    select_agent_service = _RecordingSelectAgentService()
    factory = LocalExecutionAgentFactory(select_agent_service=select_agent_service)

    runner = factory.for_execution_target(
        ExecutionTarget(kind="local_path", location="/tmp/workspace")
    )

    assert isinstance(runner, _FakeAgentRunner)
    assert select_agent_service.calls == [{}]
