"""Tests for application-layer workspace runtime composition."""

from pathlib import Path
from typing import cast

from developer.application.implementation_run_runtime import (
    WorkspaceRunOrchestratorPortAdapter,
    build_implementation_workspace_run_orchestrator,
)
from developer.application.workspace_runtime import build_workspace_orchestrator
from developer.config.service import ConfigService
from developer.forge.settings import ForgeSettings
from developer.orchestrators.runs.implementation_workspace_run_orchestrator import (
    ImplementationWorkspaceRunOrchestrator,
)
from developer.orchestrators.runs.models import WorkspaceRunCommand
from developer.version_control.settings import VersionControlSettings
from developer.workspaces.models import RunHandle, RunStatus
from developer.workspaces.settings import WorkspaceSettings


class _FakeConfigService:
    def get_config(self, section: str, config_type):
        if section == "workspaces":
            assert config_type is WorkspaceSettings
            return WorkspaceSettings(
                default_provider="git_worktree",
                state_dir=".developer/state",
                git_worktree_root_dir="developer-workspaces",
            )
        if section == "version_control":
            assert config_type is VersionControlSettings
            return VersionControlSettings(enabled=False)
        if section == "forge":
            assert config_type is ForgeSettings
            return ForgeSettings(enabled=False)
        raise AssertionError(section)


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


class _FakeWorkspaceRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def run_in_workspace(self, workspace_spec, request):
        self.calls.append((workspace_spec, request))

        class _Workspace:
            id = "workspace-1"

        return _Workspace(), RunHandle(
            id="run-1",
            workspace_id="workspace-1",
            status=RunStatus.SUCCEEDED,
            agent_kind="implementation",
            latest_message="latest update",
            metadata={"task_branch_name": "ship-it"},
        )


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
    monkeypatch.setattr(
        "developer.application.workspace_runtime._build_workspace_observer",
        lambda config_service, registry, provider: None,
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
    assert runner.agent_resolver is not None
    assert isinstance(
        runner.execution_adapter_resolver,
        _RecordingExecutionAdapterResolver,
    )
    recording_orchestrator = cast(_RecordingOrchestrator, orchestrator)
    assert recording_orchestrator.provider is provider
    assert recording_orchestrator.runner is runner


def test_workspace_run_port_adapter_translates_to_workspace_runtime() -> None:
    """The port adapter should build WorkspaceSpec and RunRequest from the command."""
    runtime = _FakeWorkspaceRuntime()

    result = WorkspaceRunOrchestratorPortAdapter(runtime).run(
        WorkspaceRunCommand(
            repo_path="/repo",
            workspace_provider="git_worktree",
            base_branch="main",
            task_id="ship-it",
            agent_kind="implementation",
            workspace_metadata={"task_branch_name": "ship-it"},
            run_context={"task_input": "docs/plans/ship-it.md"},
        )
    )

    workspace_spec, run_request = runtime.calls[-1]
    assert workspace_spec.provider == "git_worktree"
    assert workspace_spec.repo_path == "/repo"
    assert workspace_spec.base_branch == "main"
    assert workspace_spec.task_id == "ship-it"
    assert workspace_spec.metadata == {"task_branch_name": "ship-it"}
    assert run_request.agent_kind == "implementation"
    assert run_request.context == {"task_input": "docs/plans/ship-it.md"}
    assert result.workspace_id == "workspace-1"
    assert result.run_id == "run-1"
    assert result.status == "succeeded"
    assert result.latest_message == "latest update"
    assert result.metadata == {"task_branch_name": "ship-it"}


def test_build_implementation_workspace_run_orchestrator_wires_ports(
    monkeypatch,
) -> None:
    """Composition should wire infrastructure behind orchestrator-owned ports."""

    class _RecordingWorkspaceRuntime:
        pass

    runtime = _RecordingWorkspaceRuntime()
    monkeypatch.setattr(
        "developer.application.implementation_run_runtime.build_workspace_orchestrator",
        lambda config_service: runtime,
    )

    orchestrator = build_implementation_workspace_run_orchestrator(
        cast(ConfigService, _FakeConfigService())
    )

    assert isinstance(orchestrator, ImplementationWorkspaceRunOrchestrator)
    assert orchestrator._publication_store.__class__.__name__ == "FileWorkspaceRegistry"
    assert (
        orchestrator._publication_store._state_dir == Path(".developer/state").resolve()
    )
    assert (
        orchestrator._branch_inspector.__class__.__name__ == "GitVersionControlAdapter"
    )
    assert isinstance(
        orchestrator._workspace_runner,
        WorkspaceRunOrchestratorPortAdapter,
    )
    assert orchestrator._workspace_runner._workspace_runner is runtime
