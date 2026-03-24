"""Application-owned bridges between orchestrators and workspace runtime."""

from pathlib import Path

from engineeringagent.agent_backends.protocol import AgentBackendProtocol
from engineeringagent.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from engineeringagent.orchestrators.loop.implementation_agent import ImplementationAgent
from engineeringagent.orchestrators.loop.models import (
    ImplementationContext,
    OrchestratorOutcome,
)
from engineeringagent.orchestrators.loop.protocols import (
    ImplementationLifecycleObserver,
    ImplementationTask,
)
from engineeringagent.prompts.builder import OrchestratorPromptBuilder
from engineeringagent.quality.services import CheckGateRunner
from engineeringagent.tasks.select_service import TaskSelectionService
from engineeringagent.workspaces.models import (
    ExecutionTarget,
    RunRequest,
    WorkspaceRunnableResult,
    WorkspaceSession,
)
from engineeringagent.workspaces.protocols import (
    WorkspaceRunnableAgent,
    WorkspaceRunnableAgentResolver,
)


def build_implementation_agent(
    agent_runner: AgentBackendProtocol,
    task: ImplementationTask,
    *,
    max_iterations: int | None,
    observer: ImplementationLifecycleObserver | None = None,
    context: ImplementationContext | None = None,
) -> ImplementationAgent:
    """Create the shared implementation workflow graph."""
    return ImplementationAgent(
        prompt_builder=OrchestratorPromptBuilder(),
        agent_runner=agent_runner,
        gate_runner=CheckGateRunner(),
        task=task,
        observer=observer,
        context=context,
        max_iterations=max_iterations,
    )


def _build_workspace_result(outcome: OrchestratorOutcome) -> WorkspaceRunnableResult:
    """Map an implementation outcome into a workspace runtime result."""
    summary = f"iterations={outcome.iterations}"
    if outcome.status == "success":
        message = f"Implementation run succeeded after {outcome.iterations} iterations"
        metadata: dict[str, object] = {}
        if outcome.publication_message:
            message = f"{message} | {outcome.publication_message}"
            metadata["publication_message"] = outcome.publication_message
        return WorkspaceRunnableResult(
            status="succeeded",
            message=message,
            summary=summary,
            metadata=metadata,
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

    def __init__(
        self,
        agent_factory: LocalExecutionAgentFactory | None = None,
        observer: ImplementationLifecycleObserver | None = None,
    ) -> None:
        """Store the execution-target-aware agent factory and observer."""
        self._agent_factory = agent_factory or LocalExecutionAgentFactory()
        self._observer = observer

    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        """Execute the implementation loop for one workspace request."""
        agent_runner = self._agent_factory.for_execution_target(
            workspace.execution_target
        )
        task = _build_task(request, workspace)
        max_iterations = _read_max_iterations_override(request)
        context = _build_context(request, workspace, task)
        if self._observer is not None:
            self._observer.validate(context)
        outcome = build_implementation_agent(
            agent_runner,
            task=task,
            observer=self._observer,
            context=context,
            max_iterations=max_iterations,
        ).run()
        return _build_workspace_result(outcome)


class DefaultWorkspaceRunnableAgentResolver(WorkspaceRunnableAgentResolver):
    """Resolve built-in workspace-runnable workflows."""

    def __init__(
        self, implementation_agent: WorkspaceRunnableAgent | None = None
    ) -> None:
        """Allow tests and composition code to override the implementation flow."""
        self._implementation_agent = implementation_agent

    def resolve(self, agent_kind: str) -> WorkspaceRunnableAgent:
        """Return the runnable workflow for the given agent kind."""
        if agent_kind == "implementation":
            return self._implementation_agent or WorkspaceRunnableImplementationAgent()
        raise ValueError(f"Unsupported agent kind: {agent_kind}")


def _build_task(request: RunRequest, workspace: WorkspaceSession) -> ImplementationTask:
    """Re-resolve the task object from workspace run context."""
    task_input = request.context.get("task_input")
    if not isinstance(task_input, str) or not task_input:
        raise ValueError("Workspace implementation run is missing task_input")
    return TaskSelectionService().resolve(
        task_input,
        base_path=Path(workspace.execution_target.location),
    )


def _read_max_iterations_override(request: RunRequest) -> int | None:
    """Read the already-normalized max-iteration override from workspace context."""
    value = request.context.get("max_iterations")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Workspace implementation run has invalid max_iterations")
    return value


def _build_context(
    request: RunRequest,
    workspace: WorkspaceSession,
    task: ImplementationTask,
) -> ImplementationContext:
    """Build the typed implementation context for one workspace run."""
    execution_metadata = workspace.execution_target.metadata
    workspace_metadata = workspace.metadata
    return ImplementationContext(
        workspace_id=workspace.id,
        run_id=_optional_string(request.context.get("run_id")),
        repo_path=_optional_string(execution_metadata.get("repo_path")),
        workspace_path=str(workspace.execution_target.location),
        workspace_branch_name=_optional_string(
            workspace_metadata.get("workspace_branch_name")
        ),
        task_branch_name=_optional_string(workspace_metadata.get("task_branch_name")),
        base_branch=_optional_string(workspace_metadata.get("base_branch")),
        remote_name=_optional_string(workspace_metadata.get("remote_name")) or "origin",
        task_name=task.task_name,
        task_path=task.task_path,
    )


def _optional_string(value: object) -> str | None:
    """Return the value when it is a non-empty string."""
    if isinstance(value, str) and value:
        return value
    return None
