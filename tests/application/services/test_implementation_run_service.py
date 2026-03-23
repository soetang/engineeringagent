"""Tests for the implementation run application service."""

from pathlib import Path

import pytest

from developer.application.services.implementation_run_service import (
    _normalize_workspace_task_input,
    _normalize_max_iterations,
    _resolve_max_iterations,
    run_implementation,
)
from developer.config.service import ConfigService
from developer.orchestrators.loop.models import OrchestratorOutcome
from developer.orchestrators.runs.models import ImplementationWorkspaceRunOutcome


class _FakeImplementationAgent:
    def __init__(self, outcome: OrchestratorOutcome) -> None:
        self._outcome = outcome

    def run(self) -> OrchestratorOutcome:
        return self._outcome


class _FakeWorkspaceRunOrchestrator:
    def __init__(self) -> None:
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return ImplementationWorkspaceRunOutcome(
            task_name="Ship it",
            workspace_id="workspace-1",
            run_id="run-1",
            status="succeeded",
            latest_message="Implementation run succeeded after 1 iterations",
            metadata={
                "commit_shas": ["abc123"],
                "task_branch_name": "ship-it",
            },
        )


class _ResolvedTask:
    def __init__(self, task_id: str, task_path: str | None = None) -> None:
        self._task_id = task_id
        self._task_path = task_path

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def task_name(self) -> str:
        return "Ship it"

    @property
    def task_path(self) -> str | None:
        return self._task_path

    @property
    def base_branch(self) -> str | None:
        return None

    def is_complete(self):
        raise NotImplementedError

    def get_branch_name(self) -> str:
        return "ship-it"


def test_run_implementation_returns_failure_feedback(monkeypatch) -> None:
    """Direct runs should surface the last failure feedback."""
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._workspace_mode_enabled",
        lambda config_service: False,
    )
    monkeypatch.setattr(
        "developer.version_control.adapters.git_adapter.GitVersionControlAdapter.ensure_clean_checkout",
        lambda self, repo_path: None,
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.TaskSelectionService.resolve",
        lambda self, task_input, base_path=None: _ResolvedTask(
            "ship-it", task_path=str(Path("docs/plans/ship-it.md"))
        ),
    )
    monkeypatch.setattr(
        "developer.agent_backends.select_agent_backend_service.SelectAgentBackendService.select_agent",
        lambda self: object(),
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.build_implementation_agent",
        lambda agent_runner, task, max_iterations=None: _FakeImplementationAgent(
            OrchestratorOutcome(
                status="failed",
                iterations=3,
                feedback="ruff check failed",
            )
        ),
    )

    result = run_implementation(task_input="docs/plans/ship-it.md")

    assert result.exit_code == 1
    assert result.message == "Implementation run failed: ruff check failed"


def test_workspace_run_formats_task_and_commit_count(monkeypatch, tmp_path) -> None:
    """Workspace runs should include task and commit metadata in the final message."""
    fake_orchestrator = _FakeWorkspaceRunOrchestrator()
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._workspace_mode_enabled",
        lambda config_service: True,
    )
    monkeypatch.setattr(
        "developer.version_control.adapters.git_adapter.GitVersionControlAdapter.ensure_clean_checkout",
        lambda self, repo_path: None,
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.TaskSelectionService.resolve",
        lambda self, task_input, base_path=None: _ResolvedTask(
            "ship-it", task_path=str(Path("docs/plans/ship-it.md"))
        ),
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.build_implementation_workspace_run_orchestrator",
        lambda config_service: fake_orchestrator,
    )

    config_file = tmp_path / "engineeringagent.toml"
    config_file.write_text(
        """[implementation]
max_iterations = 40

[workspaces]
default_provider = "git_worktree"
state_dir = ".developer/state"
git_worktree_root_dir = "developer-workspaces"
""",
        encoding="utf-8",
    )

    result = run_implementation(
        task_input="docs/plans/ship-it.md",
        max_iterations=20,
        config_service=ConfigService(config_file=str(config_file)),
    )

    assert result.exit_code == 0
    assert "task=Ship it" in result.message
    assert "commits=1" in result.message
    assert "branch=ship-it" in result.message
    assert len(fake_orchestrator.requests) == 1
    request = fake_orchestrator.requests[0]
    assert request.repo_path == str(Path.cwd())
    assert request.task is not None
    assert request.task.task_name == "Ship it"
    assert request.normalized_task_input == "docs/plans/ship-it.md"
    assert request.max_iterations == 20
    assert not hasattr(request, "agent_kind")


def test_workspace_run_uses_caller_checkout_for_repo_path(
    monkeypatch, tmp_path
) -> None:
    """Workspace requests should take repo_path from the current checkout."""
    fake_orchestrator = _FakeWorkspaceRunOrchestrator()
    workspace_repo = tmp_path / "workspace-checkout"
    workspace_repo.mkdir()
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._workspace_mode_enabled",
        lambda config_service: True,
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.Path.cwd",
        lambda: workspace_repo,
    )
    monkeypatch.setattr(
        "developer.version_control.adapters.git_adapter.GitVersionControlAdapter.ensure_clean_checkout",
        lambda self, repo_path: None,
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.TaskSelectionService.resolve",
        lambda self, task_input, base_path=None: _ResolvedTask(
            "ship-it", task_path="/different/task/location.md"
        ),
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.build_implementation_workspace_run_orchestrator",
        lambda config_service: fake_orchestrator,
    )

    config_file = tmp_path / "engineeringagent.toml"
    config_file.write_text(
        """[implementation]
max_iterations = 40

[workspaces]
default_provider = "git_worktree"
state_dir = ".developer/state"
git_worktree_root_dir = "developer-workspaces"
""",
        encoding="utf-8",
    )

    run_implementation(
        task_input="docs/plans/ship-it.md",
        config_service=ConfigService(config_file=str(config_file)),
    )

    request = fake_orchestrator.requests[0]
    assert request.repo_path == str(workspace_repo)
    assert request.task.task_path == "/different/task/location.md"


def test_run_implementation_fails_when_checkout_is_dirty(monkeypatch) -> None:
    """Implement should fail before resolution when the checkout is dirty."""
    monkeypatch.setattr(
        "developer.version_control.adapters.git_adapter.GitVersionControlAdapter.ensure_clean_checkout",
        lambda self, repo_path: (_ for _ in ()).throw(ValueError("dirty checkout")),
    )

    result = run_implementation(task_input="docs/plans/ship-it.md")

    assert result.exit_code == 1
    assert result.message == "dirty checkout"


def test_normalize_max_iterations_accepts_infinite() -> None:
    """Infinite iteration settings should normalize to None."""
    assert _normalize_max_iterations("infinite", source="config") is None


@pytest.mark.parametrize("value", [0, -1, "zero"])
def test_normalize_max_iterations_rejects_invalid_values(value) -> None:
    """Iteration settings should reject invalid values."""
    with pytest.raises(ValueError, match="positive integer or 'infinite'"):
        _normalize_max_iterations(value, source="config")


def test_resolve_max_iterations_prefers_cli_override(tmp_path) -> None:
    """CLI overrides should take precedence over config values."""
    config_file = tmp_path / "engineeringagent.toml"
    config_file.write_text(
        """[implementation]
max_iterations = 10
""",
        encoding="utf-8",
    )

    resolved = _resolve_max_iterations(
        ConfigService(config_file=str(config_file)),
        cli_override=20,
    )

    assert resolved == 20


def test_normalize_workspace_task_input_rewrites_repo_absolute_paths(tmp_path) -> None:
    """Workspace task input should stay relative when it points inside the repo."""
    task_path = tmp_path / "docs/plans/ship-it.md"
    task_path.parent.mkdir(parents=True)
    task_path.write_text("plan", encoding="utf-8")

    normalized = _normalize_workspace_task_input(tmp_path, str(task_path))

    assert normalized == "docs/plans/ship-it.md"
