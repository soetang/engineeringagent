"""Application service for implementation runs."""

from pathlib import Path
from uuid import uuid4

from developer.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from developer.application.models import ImplementationRunResult
from developer.application.settings import ImplementationSettings
from developer.application.workspace_bridges import build_implementation_agent
from developer.application.workspace_runtime import build_workspace_orchestrator
from developer.config.service import ConfigService
from developer.orchestrators.models import OrchestratorOutcome
from developer.tasks.errors import TaskError
from developer.tasks.models import TaskPublicationState
from developer.tasks.protocol import ImplementationTask
from developer.tasks.select_service import TaskSelectionService
from developer.version_control.adapters.git_adapter import GitVersionControlAdapter
from developer.workspaces.models import RunHandle, RunRequest, WorkspaceSpec
from developer.workspaces.services.file_registry import FileWorkspaceRegistry
from developer.workspaces.settings import WorkspaceSettings

IMPLEMENTATION_AGENT_KIND = "implementation"
MAX_ITERATIONS_HELP = "Use a positive integer or 'infinite'"


def run_implementation(
    task_input: str,
    max_iterations: int | str | None = None,
    config_service: ConfigService | None = None,
) -> ImplementationRunResult:
    """Run the implementation workflow using the configured execution mode."""
    resolved_config_service = config_service or ConfigService()
    repo_path = Path.cwd()
    version_control = GitVersionControlAdapter()
    try:
        version_control.ensure_clean_checkout(str(repo_path))
        task = TaskSelectionService().resolve(task_input, base_path=repo_path)
        resolved_max_iterations = _resolve_max_iterations(
            resolved_config_service,
            cli_override=max_iterations,
        )
    except (ValueError, TaskError) as exc:
        return ImplementationRunResult(exit_code=1, message=str(exc))

    if _workspace_mode_enabled(resolved_config_service):
        return _run_implementation_in_workspace(
            resolved_config_service,
            task,
            task_input=task_input,
            max_iterations=resolved_max_iterations,
        )

    outcome = build_implementation_agent(
        SelectAgentBackendService(resolved_config_service).select_agent(),
        task=task,
        max_iterations=resolved_max_iterations,
    ).run()
    return _build_direct_run_result(outcome)


def _workspace_mode_enabled(config_service: ConfigService) -> bool:
    """Return whether the workspace execution path is configured."""
    return config_service.has_section("workspaces")


def _run_implementation_in_workspace(
    config_service: ConfigService,
    task: ImplementationTask,
    *,
    task_input: str,
    max_iterations: int | None,
) -> ImplementationRunResult:
    """Run the implementation workflow through workspace orchestration."""
    repo_path = Path.cwd()
    version_control = GitVersionControlAdapter()
    base_branch = version_control.get_current_branch(str(repo_path))
    publication = _load_task_publication(config_service, task)
    publication_branch = _resolve_task_branch(
        repo_path,
        task,
        publication,
        version_control=version_control,
    )
    workspace_start_point = _resolve_workspace_start_point(
        publication=publication,
        base_branch=base_branch,
    )
    workspace_metadata = {
        "task_id": task.task_id,
        "task_name": task.task_name,
        "task_path": task.task_path,
        "task_branch_name": publication_branch,
        "remote_name": "origin",
        "start_point": workspace_start_point,
    }
    request_context = {
        "task_input": _normalize_workspace_task_input(repo_path, task_input),
        "task_id": task.task_id,
        "task_name": task.task_name,
        "task_path": task.task_path,
        "task_branch_name": publication_branch,
        "max_iterations": max_iterations,
    }
    workspace, run_handle = build_workspace_orchestrator(
        config_service
    ).run_in_workspace(
        WorkspaceSpec(
            provider="git_worktree",
            repo_path=str(repo_path),
            base_branch=base_branch,
            task_id=task.task_id,
            metadata=workspace_metadata,
        ),
        RunRequest(
            agent_kind=IMPLEMENTATION_AGENT_KIND,
            context=request_context,
        ),
    )
    return ImplementationRunResult(
        exit_code=0 if run_handle.status.value == "succeeded" else 1,
        message=_format_workspace_run_message(workspace.id, run_handle, task.task_name),
    )


def _load_task_publication(
    config_service: ConfigService,
    task: ImplementationTask,
) -> TaskPublicationState | None:
    """Load any persisted publication state for the task."""
    settings = config_service.get_config("workspaces", WorkspaceSettings)
    registry = FileWorkspaceRegistry(Path(settings.state_dir).resolve())
    return registry.get_task_publication(task.task_name, task.task_path)


def _resolve_task_branch(
    repo_path: Path,
    task: ImplementationTask,
    publication: TaskPublicationState | None,
    *,
    version_control: GitVersionControlAdapter,
) -> str:
    """Resolve the publication branch for the current task run."""
    if publication is not None:
        return publication.branch_name

    candidate = task.get_branch_name()
    if not version_control.branch_exists(
        str(repo_path),
        candidate,
        remote_name="origin",
    ):
        return candidate
    return f"{candidate}-{uuid4().hex[:8]}"


def _resolve_workspace_start_point(
    publication: TaskPublicationState | None,
    base_branch: str,
) -> str:
    """Choose the branch or ref used to seed the disposable workspace branch."""
    if publication is not None:
        return publication.branch_name
    return base_branch


def _format_workspace_run_message(
    workspace_id: str,
    run_handle: RunHandle,
    task_name: str,
) -> str:
    """Build the final workspace run status line."""
    metadata = run_handle.metadata
    parts = [
        f"workspace={workspace_id}",
        f"run={run_handle.id}",
        f"task={task_name}",
        f"status={run_handle.status.value}",
    ]
    commit_shas = metadata.get("commit_shas", [])
    if isinstance(commit_shas, list) and commit_shas:
        parts.append(f"commits={len(commit_shas)}")
    branch = metadata.get("pushed_branch") or metadata.get("task_branch_name")
    if isinstance(branch, str) and branch:
        parts.append(f"branch={branch}")
    pr_url = metadata.get("pr_url")
    if isinstance(pr_url, str) and pr_url:
        parts.append(f"pr={pr_url}")
    if run_handle.latest_message:
        parts.append(run_handle.latest_message)
    message = " | ".join(parts)
    if isinstance(pr_url, str) and pr_url:
        return f"{message}\nPull request: {pr_url}"
    return message


def _resolve_max_iterations(
    config_service: ConfigService,
    *,
    cli_override: int | str | None,
) -> int | None:
    """Resolve max iterations from CLI override, config, or defaults."""
    if cli_override is not None:
        return _normalize_max_iterations(cli_override, source="CLI --max-iterations")
    settings = config_service.get_config("implementation", ImplementationSettings)
    return _normalize_max_iterations(settings.max_iterations, source="config")


def _normalize_max_iterations(value: int | str, *, source: str) -> int | None:
    """Normalize finite and infinite iteration settings."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "infinite":
            return None
        if normalized.isdigit():
            value = int(normalized)
        else:
            raise _invalid_max_iterations_error(source, value)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _invalid_max_iterations_error(source, value)
    return value


def _build_direct_run_result(
    outcome: OrchestratorOutcome,
) -> ImplementationRunResult:
    """Convert a direct orchestrator outcome into a CLI-facing result."""
    if outcome.status == "success":
        return ImplementationRunResult(
            exit_code=0, message="Implementation run succeeded"
        )

    message = "Implementation run failed"
    if outcome.feedback:
        message = f"{message}: {outcome.feedback}"
    return ImplementationRunResult(exit_code=1, message=message)


def _invalid_max_iterations_error(source: str, value: object) -> ValueError:
    """Build a consistent max-iterations validation error."""
    return ValueError(
        f"Invalid {source} max_iterations value: {value}. {MAX_ITERATIONS_HELP}"
    )


def _normalize_workspace_task_input(repo_path: Path, task_input: str) -> str:
    """Store a workspace-safe task input path relative to the repository."""
    normalized = task_input[1:] if task_input.startswith("@") else task_input
    candidate = Path(normalized).expanduser()
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(repo_path.resolve())
        except ValueError:
            return str(candidate.resolve())
    return str(candidate)
