"""Application-owned bridges between orchestrators and workspace runtime."""

from developer.agent_backends.protocol import AgentBackendProtocol
from developer.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from developer.orchestrators.implementation_agent import ImplementationAgent
from developer.orchestrators.models import ImplementationContext, OrchestratorOutcome
from developer.orchestrators.protocols import ImplementationLifecycleObserver
from developer.prompts.builder import OrchestratorPromptBuilder
from developer.quality.services import CheckGateRunner
from developer.tasks.implementation_task import SimpleImplementationTask
from developer.tasks.protocol import ImplementationTask
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
    task: ImplementationTask,
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
        task = _build_task(request)
        context = _build_context(request, workspace, task)
        if self._observer is not None:
            self._observer.validate(context)
        outcome = build_implementation_agent(
            agent_runner,
            task=task,
            observer=self._observer,
            context=context,
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


def _build_task(request: RunRequest) -> SimpleImplementationTask:
    """Create the mock task object from the run request."""
    task_name = str(request.context["task_name"])
    task_path = request.context.get("task_path")
    normalized_task_path = str(task_path) if isinstance(task_path, str) else None
    return SimpleImplementationTask(task_name, task_path=normalized_task_path)


def _build_context(
    request: RunRequest,
    workspace: WorkspaceSession,
    task: ImplementationTask,
) -> ImplementationContext:
    """Build the typed implementation context for one workspace run."""
    repo_path = workspace.execution_target.metadata.get("repo_path")
    normalized_repo_path = str(repo_path) if isinstance(repo_path, str) else None
    run_id = request.context.get("run_id")
    normalized_run_id = str(run_id) if isinstance(run_id, str) else None
    return ImplementationContext(
        workspace_id=workspace.id,
        run_id=normalized_run_id,
        repo_path=normalized_repo_path,
        workspace_path=str(workspace.execution_target.location),
        workspace_branch_name=_optional_string(
            workspace.metadata.get("workspace_branch_name")
        ),
        task_branch_name=_optional_string(workspace.metadata.get("task_branch_name")),
        base_branch=_optional_string(workspace.metadata.get("base_branch")),
        remote_name=_optional_string(workspace.metadata.get("remote_name")) or "origin",
        task_name=task.identity.name,
        task_path=task.identity.path,
    )


def _optional_string(value: object) -> str | None:
    """Return the value when it is a non-empty string."""
    if isinstance(value, str) and value:
        return value
    return None
