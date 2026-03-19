"""Application-owned bridges between orchestrators and workspace runtime."""

from developer.agent_backends.protocol import AgentBackendProtocol
from developer.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from developer.orchestrators.implementation_agent import ImplementationAgent
from developer.orchestrators.models import OrchestratorOutcome
from developer.prompts.builder import OrchestratorPromptBuilder
from developer.quality.services import CheckGateRunner
from developer.tasks.implementation_judge import ImplementationJudge
from developer.workspaces.models import (
    ExecutionTarget,
    RunRequest,
    WorkspaceRunnableResult,
    WorkspaceSession,
)
from developer.workspaces.protocols import (
    WorkspaceRunnableAgent,
    WorkspaceRunnableAgentResolver,
)


def build_implementation_agent(
    agent_runner: AgentBackendProtocol,
) -> ImplementationAgent:
    """Create the shared implementation workflow graph."""
    return ImplementationAgent(
        prompt_builder=OrchestratorPromptBuilder(),
        agent_runner=agent_runner,
        gate_runner=CheckGateRunner(),
        completion_judge=ImplementationJudge(),
    )


def _build_workspace_result(outcome: OrchestratorOutcome) -> WorkspaceRunnableResult:
    """Map an implementation outcome into a workspace runtime result."""
    summary = f"iterations={outcome.iterations}"
    if outcome.status == "success":
        return WorkspaceRunnableResult(
            status="succeeded",
            message=(
                f"Implementation run succeeded after {outcome.iterations} iterations"
            ),
            summary=summary,
        )

    message = f"Implementation run failed after {outcome.iterations} iterations"
    if outcome.feedback:
        message = f"{message}: {outcome.feedback}"
    return WorkspaceRunnableResult(
        status="failed",
        message=message,
        summary=summary,
    )


class LocalExecutionAgentFactory:
    """Create concrete agent runners from execution targets."""

    def __init__(
        self,
        select_agent_backend_service: SelectAgentBackendService | None = None,
    ) -> None:
        """Create a factory backed by the normal agent selection service."""
        self._select_agent_backend_service = (
            select_agent_backend_service or SelectAgentBackendService()
        )

    def for_execution_target(self, target: ExecutionTarget) -> AgentBackendProtocol:
        """Return an agent runner for the requested execution target."""
        if target.kind == "local_path":
            return self._select_agent_backend_service.select_agent()
        raise ValueError(f"Unsupported execution target kind: {target.kind}")


class WorkspaceRunnableImplementationAgent(WorkspaceRunnableAgent):
    """Run the implementation workflow inside a workspace."""

    def __init__(self, agent_factory: LocalExecutionAgentFactory | None = None) -> None:
        """Store the execution-target-aware agent factory."""
        self._agent_factory = agent_factory or LocalExecutionAgentFactory()

    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        """Execute the implementation loop for one workspace request."""
        del request
        agent_runner = self._agent_factory.for_execution_target(
            workspace.execution_target
        )
        outcome = build_implementation_agent(agent_runner).run()
        return _build_workspace_result(outcome)


class DefaultWorkspaceRunnableAgentResolver(WorkspaceRunnableAgentResolver):
    """Resolve built-in workspace-runnable workflows."""

    def resolve(self, agent_kind: str) -> WorkspaceRunnableAgent:
        """Return the runnable workflow for the given agent kind."""
        if agent_kind == "implementation":
            return WorkspaceRunnableImplementationAgent()
        raise ValueError(f"Unsupported agent kind: {agent_kind}")
