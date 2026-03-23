"""Application service for implementation runs."""

from pathlib import Path

from developer.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from developer.application.implementation_run_runtime import (
    build_implementation_workspace_run_orchestrator,
)
from developer.application.models import ImplementationRunResult
from developer.application.settings import ImplementationSettings
from developer.application.workspace_bridges import build_implementation_agent
from developer.config.service import ConfigService
from developer.orchestrators.loop.models import OrchestratorOutcome
from developer.orchestrators.runs.models import (
    ImplementationWorkspaceRunOutcome,
    ImplementationWorkspaceRunRequest,
)
from developer.tasks.errors import TaskError
from developer.tasks.select_service import TaskSelectionService
from developer.version_control.adapters.git_adapter import GitVersionControlAdapter

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
    task,
    *,
    task_input: str,
    max_iterations: int | None,
) -> ImplementationRunResult:
    """Run the implementation workflow through workspace orchestration."""
    repo_path = Path.cwd()
    outcome = build_implementation_workspace_run_orchestrator(config_service).run(
        ImplementationWorkspaceRunRequest(
            repo_path=str(repo_path),
            normalized_task_input=_normalize_workspace_task_input(
                repo_path, task_input
            ),
            task=task,
            max_iterations=max_iterations,
        )
    )
    return _build_workspace_run_result(outcome)


def _build_workspace_run_result(
    outcome: ImplementationWorkspaceRunOutcome,
) -> ImplementationRunResult:
    """Build the final workspace run status line."""
    metadata = outcome.metadata
    parts = [
        f"workspace={outcome.workspace_id}",
        f"run={outcome.run_id}",
        f"task={outcome.task_name}",
        f"status={outcome.status}",
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
    if outcome.latest_message:
        parts.append(outcome.latest_message)
    message = " | ".join(parts)
    if isinstance(pr_url, str) and pr_url:
        message = f"{message}\nPull request: {pr_url}"
    return ImplementationRunResult(
        exit_code=0 if outcome.status == "succeeded" else 1,
        message=message,
    )


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
