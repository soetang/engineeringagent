"""Tests for application-layer workspace runtime composition."""

from pathlib import Path
from typing import cast

from developer.application.workspace_runtime import build_workspace_orchestrator
from developer.config.service import ConfigService
from developer.workspaces.settings import WorkspaceSettings


class _FakeConfigService:
    def get_config(
        self, section: str, config_type: type[WorkspaceSettings]
    ) -> WorkspaceSettings:
        assert section == "workspaces"
        assert config_type is WorkspaceSettings
        return WorkspaceSettings(
            default_provider="git_worktree",
            state_dir=".developer/state",
            git_worktree_root_dir="developer-workspaces",
        )


class _RecordingRegistry:
    instances: list["_RecordingRegistry"] = []

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.__class__.instances.append(self)


class _RecordingProvider:
    instances: list["_RecordingProvider"] = []

    def __init__(self, workspaces_root: Path, registry) -> None:
        self.workspaces_root = workspaces_root
        self.registry = registry
        self.__class__.instances.append(self)


class _RecordingAgentResolver:
    instances: list["_RecordingAgentResolver"] = []

    def __init__(self) -> None:
        self.__class__.instances.append(self)


class _RecordingExecutionAdapterResolver:
    instances: list["_RecordingExecutionAdapterResolver"] = []

    def __init__(self) -> None:
        self.__class__.instances.append(self)


class _RecordingRunner:
    instances: list["_RecordingRunner"] = []

    def __init__(self, registry, agent_resolver, execution_adapter_resolver) -> None:
        self.registry = registry
        self.agent_resolver = agent_resolver
        self.execution_adapter_resolver = execution_adapter_resolver
        self.__class__.instances.append(self)


class _RecordingOrchestrator:
    instances: list["_RecordingOrchestrator"] = []

    def __init__(self, provider, runner) -> None:
        self.provider = provider
        self.runner = runner
        self.__class__.instances.append(self)


def test_build_workspace_orchestrator_wires_runtime_dependencies(monkeypatch) -> None:
    """Composition should wire the bridge resolver and execution adapter resolver."""
    monkeypatch.setattr(
        "developer.application.workspace_runtime.FileWorkspaceRegistry",
        _RecordingRegistry,
    )
    monkeypatch.setattr(
        "developer.application.workspace_runtime.GitWorktreeWorkspaceProvider",
        _RecordingProvider,
    )
    monkeypatch.setattr(
        "developer.application.workspace_runtime.DefaultWorkspaceRunnableAgentResolver",
        _RecordingAgentResolver,
    )
    monkeypatch.setattr(
        "developer.application.workspace_runtime.DefaultWorkspaceExecutionAdapterResolver",
        _RecordingExecutionAdapterResolver,
    )
    monkeypatch.setattr(
        "developer.application.workspace_runtime.LocalProcessWorkspaceRunner",
        _RecordingRunner,
    )
    monkeypatch.setattr(
        "developer.application.workspace_runtime.WorkspaceRunOrchestrator",
        _RecordingOrchestrator,
    )

    orchestrator = build_workspace_orchestrator(
        cast(ConfigService, _FakeConfigService())
    )

    registry = _RecordingRegistry.instances[-1]
    provider = _RecordingProvider.instances[-1]
    runner = _RecordingRunner.instances[-1]

    assert orchestrator is _RecordingOrchestrator.instances[-1]
    assert registry.state_dir == Path(".developer/state").resolve()
    assert provider.workspaces_root == Path("developer-workspaces").resolve()
    assert provider.registry is registry
    assert runner.registry is registry
    assert isinstance(runner.agent_resolver, _RecordingAgentResolver)
    assert isinstance(
        runner.execution_adapter_resolver,
        _RecordingExecutionAdapterResolver,
    )
    recording_orchestrator = cast(_RecordingOrchestrator, orchestrator)
    assert recording_orchestrator.provider is provider
    assert recording_orchestrator.runner is runner
