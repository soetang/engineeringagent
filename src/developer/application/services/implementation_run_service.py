"""Application service for implementation runs."""

import subprocess
from pathlib import Path
from uuid import uuid4

from developer.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from developer.application.models import ImplementationRunResult
from developer.application.workspace_bridges import build_implementation_agent
from developer.application.workspace_runtime import build_workspace_orchestrator
from developer.config.service import ConfigService
from developer.tasks.implementation_task import SimpleImplementationTask
from developer.tasks.models import TaskPublicationState
from developer.workspaces.models import RunHandle, RunRequest, WorkspaceSpec
from developer.workspaces.services.file_registry import FileWorkspaceRegistry
from developer.workspaces.settings import WorkspaceSettings

IMPLEMENTATION_AGENT_KIND = "implementation"


def run_implementation(
    task_name: str,
    config_service: ConfigService | None = None,
) -> ImplementationRunResult:
    """Run the implementation workflow using the configured execution mode."""
    resolved_config_service = config_service or ConfigService()
    task = SimpleImplementationTask(task_name)
    if _workspace_mode_enabled(resolved_config_service):
        return _run_implementation_in_workspace(resolved_config_service, task)

    outcome = build_implementation_agent(
        SelectAgentBackendService(resolved_config_service).select_agent(),
        task=task,
    ).run()
    if outcome.status == "success":
        return ImplementationRunResult(
            exit_code=0, message="Implementation run succeeded"
        )
    failure_message = "Implementation run failed"
    if outcome.feedback:
        failure_message = f"{failure_message}: {outcome.feedback}"
    return ImplementationRunResult(exit_code=1, message=failure_message)


def _workspace_mode_enabled(config_service: ConfigService) -> bool:
    """Return whether the workspace execution path is configured."""
    return config_service.has_section("workspaces")


def _run_implementation_in_workspace(
    config_service: ConfigService,
    task: SimpleImplementationTask,
) -> ImplementationRunResult:
    """Run the implementation workflow through workspace orchestration."""
    repo_path = Path.cwd()
    base_branch = _resolve_current_branch(repo_path)
    publication = _load_task_publication(config_service, task)
    publication_branch = _resolve_task_branch(repo_path, task, publication)
    workspace_start_point = _resolve_workspace_start_point(
        publication=publication,
        base_branch=base_branch,
    )
    workspace, run_handle = build_workspace_orchestrator(
        config_service
    ).run_in_workspace(
        WorkspaceSpec(
            provider="git_worktree",
            repo_path=str(repo_path),
            base_branch=base_branch,
            task_id=task.task_name,
            metadata={
                "task_name": task.task_name,
                "task_path": task.task_path,
                "task_branch_name": publication_branch,
                "remote_name": "origin",
                "start_point": workspace_start_point,
            },
        ),
        RunRequest(
            agent_kind=IMPLEMENTATION_AGENT_KIND,
            context={
                "task_name": task.task_name,
                "task_path": task.task_path,
                "task_branch_name": publication_branch,
            },
        ),
    )
    return ImplementationRunResult(
        exit_code=0 if run_handle.status.value == "succeeded" else 1,
        message=_format_workspace_run_message(workspace.id, run_handle, task.task_name),
    )


def _load_task_publication(
    config_service: ConfigService,
    task: SimpleImplementationTask,
) -> TaskPublicationState | None:
    """Load any persisted publication state for the task."""
    settings = config_service.get_config("workspaces", WorkspaceSettings)
    registry = FileWorkspaceRegistry(Path(settings.state_dir).resolve())
    return registry.get_task_publication(task.task_name, task.task_path)


def _resolve_task_branch(
    repo_path: Path,
    task: SimpleImplementationTask,
    publication: TaskPublicationState | None,
) -> str:
    """Resolve the publication branch for the current task run."""
    if publication is not None:
        return publication.branch_name

    candidate = task.get_branch_name()
    if not _branch_exists(repo_path, candidate, remote_name="origin"):
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


def _resolve_current_branch(repo_path: Path) -> str:
    """Return the currently checked out branch for the given repository."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    branch = result.stdout.strip()
    return branch or "main"


def _branch_exists(repo_path: Path, branch_name: str, remote_name: str) -> bool:
    """Return whether the candidate publication branch already exists."""
    local = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if local.returncode == 0:
        return True

    remote = subprocess.run(
        ["git", "ls-remote", "--heads", remote_name, branch_name],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return remote.returncode == 0 and bool(remote.stdout.strip())
