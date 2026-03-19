"""Application-layer workspace runtime composition helpers."""

import os
from contextlib import contextmanager
from pathlib import Path

from developer.agents.protocol import AgentProtocol
from developer.agents.select_agent_service import SelectAgentService
from developer.config.service import ConfigService
from developer.orchestrators.implementation_agent import ImplementationAgent
from developer.orchestrators.workspace_protocols import (
    WorkspaceRunnableAgent,
    WorkspaceRunnableAgentResolver,
)
from developer.orchestrators.workspace_run_orchestrator import WorkspaceRunOrchestrator
from developer.prompts.builder import OrchestratorPromptBuilder
from developer.quality.services import CheckGateRunner
from developer.tasks.implementation_judge import ImplementationJudge
from developer.workspaces.adapters.git_worktree_provider import (
    GitWorktreeWorkspaceProvider,
)
from developer.workspaces.adapters.local_process_runner import (
    LocalProcessWorkspaceRunner,
)
from developer.workspaces.models import (
    ExecutionTarget,
    RunRequest,
    WorkspaceRunnableResult,
    WorkspaceSession,
)
from developer.workspaces.services.file_registry import FileWorkspaceRegistry
from developer.workspaces.settings import WorkspaceSettings


def build_implementation_agent(agent_runner: AgentProtocol) -> ImplementationAgent:
    """Create the shared implementation workflow graph."""
    return ImplementationAgent(
        prompt_builder=OrchestratorPromptBuilder(),
        agent_runner=agent_runner,
        gate_runner=CheckGateRunner(),
        completion_judge=ImplementationJudge(),
    )


class LocalExecutionAgentFactory:
    """Create concrete agent runners from execution targets."""

    def __init__(self, select_agent_service: SelectAgentService | None = None) -> None:
        """Create a factory backed by the normal agent selection service."""
        self._select_agent_service = select_agent_service or SelectAgentService()

    def for_execution_target(self, target: ExecutionTarget) -> AgentProtocol:
        """Return an agent runner for the requested execution target."""
        if target.kind == "local_path":
            return self._select_agent_service.select_agent()
        raise ValueError(f"Unsupported execution target kind: {target.kind}")


class WorkspaceRunnableImplementationAgent(WorkspaceRunnableAgent):
    """Run the existing implementation workflow inside a workspace."""

    def __init__(self, agent_factory: LocalExecutionAgentFactory | None = None) -> None:
        """Store the execution-target-aware agent factory."""
        self._agent_factory = agent_factory or LocalExecutionAgentFactory()

    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        """Execute the implementation loop in the workspace checkout."""
        del request
        workspace_root = Path(workspace.execution_target.location)
        with _working_directory(workspace_root):
            outcome = build_implementation_agent(
                self._agent_factory.for_execution_target(workspace.execution_target)
            ).run()
        if outcome.status == "success":
            return WorkspaceRunnableResult(
                status="succeeded",
                message=f"Implementation run succeeded after {outcome.iterations} iterations",
                summary=f"iterations={outcome.iterations}",
            )
        failure_message = (
            f"Implementation run failed after {outcome.iterations} iterations"
        )
        if outcome.feedback:
            failure_message = f"{failure_message}: {outcome.feedback}"
        return WorkspaceRunnableResult(
            status="failed",
            message=failure_message,
            summary=f"iterations={outcome.iterations}",
        )


class DefaultWorkspaceRunnableAgentResolver(WorkspaceRunnableAgentResolver):
    """Resolve built-in workspace-runnable workflows."""

    def resolve(self, agent_kind: str) -> WorkspaceRunnableAgent:
        """Return the runnable workflow for the given agent kind."""
        if agent_kind == "implementation":
            return WorkspaceRunnableImplementationAgent()
        raise ValueError(f"Unsupported agent kind: {agent_kind}")


def build_workspace_orchestrator(
    config_service: ConfigService | None = None,
) -> WorkspaceRunOrchestrator:
    """Create the default workspace-backed implementation orchestrator."""
    resolved_config_service = config_service or ConfigService()
    settings = resolved_config_service.get_config("workspaces", WorkspaceSettings)
    registry = FileWorkspaceRegistry(Path(settings.state_dir).resolve())
    provider = GitWorktreeWorkspaceProvider(
        workspaces_root=Path(settings.git_worktree_root_dir).resolve(),
        registry=registry,
    )
    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=DefaultWorkspaceRunnableAgentResolver(),
    )
    return WorkspaceRunOrchestrator(provider, runner)


@contextmanager
def _working_directory(path: Path):
    """Temporarily change the process working directory."""
    previous_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous_cwd)
