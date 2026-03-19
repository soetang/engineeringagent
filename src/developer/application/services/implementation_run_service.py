"""Application service for implementation runs."""

import subprocess
from pathlib import Path
from uuid import uuid4

from developer.agents.select_agent_service import SelectAgentService
from developer.application.models import ImplementationRunResult
from developer.application.workspace_runtime import (
    build_implementation_agent,
    build_workspace_orchestrator,
)
from developer.config.service import ConfigService
from developer.workspaces.models import RunRequest, WorkspaceSpec


def run_implementation(
    config_service: ConfigService | None = None,
) -> ImplementationRunResult:
    """Run the implementation workflow using the configured execution mode."""
    resolved_config_service = config_service or ConfigService()
    if _workspace_mode_enabled(resolved_config_service):
        repo_path = Path.cwd()
        workspace, run_handle = build_workspace_orchestrator(
            resolved_config_service
        ).run_in_workspace(
            WorkspaceSpec(
                provider="git_worktree",
                repo_path=str(repo_path),
                base_branch=_resolve_current_branch(repo_path),
                task_id=f"implementation-{uuid4().hex[:8]}",
            ),
            RunRequest(agent_kind="implementation", context={}),
        )
        return ImplementationRunResult(
            exit_code=0 if run_handle.status.value == "succeeded" else 1,
            message=" | ".join(
                [
                    f"workspace={workspace.id}",
                    f"run={run_handle.id}",
                    f"status={run_handle.status.value}",
                    run_handle.latest_message or "No message available",
                ]
            ),
        )

    outcome = build_implementation_agent(SelectAgentService().select_agent()).run()
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
