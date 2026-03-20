"""Tests for the implementation run application service."""

from pathlib import Path

import pytest

from developer.application.services.implementation_run_service import (
    _normalize_max_iterations,
    _resolve_max_iterations,
    _resolve_task_branch,
    _resolve_workspace_start_point,
    run_implementation,
)
from developer.config.service import ConfigService
from developer.orchestrators.loop.models import OrchestratorOutcome
from developer.tasks.models import TaskPublicationState
from developer.version_control.adapters.git_adapter import GitVersionControlAdapter
from developer.workspaces.models import RunHandle, RunStatus


class _FakeImplementationAgent:
    def __init__(self, outcome: OrchestratorOutcome) -> None:
        self._outcome = outcome

    def run(self) -> OrchestratorOutcome:
        return self._outcome


class _FakeWorkspaceOrchestrator:
    def run_in_workspace(self, workspace_spec, request):
        assert workspace_spec.metadata["task_branch_name"] == "ship-it"
        assert request.context["task_input"] == "docs/plans/ship-it.md"
        assert request.context["max_iterations"] == 20

        class _Workspace:
            id = "workspace-1"

        return _Workspace(), RunHandle(
            id="run-1",
            workspace_id="workspace-1",
            status=RunStatus.SUCCEEDED,
            agent_kind="implementation",
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
        "developer.application.services.implementation_run_service.build_workspace_orchestrator",
        lambda config_service: _FakeWorkspaceOrchestrator(),
    )
    monkeypatch.setattr(
        "developer.version_control.adapters.git_adapter.GitVersionControlAdapter.get_current_branch",
        lambda self, repo_path: "main",
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._resolve_task_branch",
        lambda repo_path, task, publication, version_control: task.get_branch_name(),
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


def test_run_implementation_fails_when_checkout_is_dirty(monkeypatch) -> None:
    """Implement should fail before resolution when the checkout is dirty."""
    monkeypatch.setattr(
        "developer.version_control.adapters.git_adapter.GitVersionControlAdapter.ensure_clean_checkout",
        lambda self, repo_path: (_ for _ in ()).throw(ValueError("dirty checkout")),
    )

    result = run_implementation(task_input="docs/plans/ship-it.md")

    assert result.exit_code == 1
    assert result.message == "dirty checkout"


def test_resolve_task_branch_reuses_existing_publication() -> None:
    """Existing publication state should own future branch reuse."""
    task = _ResolvedTask("ship-it", task_path="/tmp/plan.md")
    publication = TaskPublicationState(
        task_name="ship-it",
        task_path="/tmp/plan.md",
        branch_name="published-branch",
        base_branch="main",
        status="created",
    )

    branch = _resolve_task_branch(
        Path("."),
        task,
        publication,
        version_control=GitVersionControlAdapter(),
    )

    assert branch == "published-branch"


def test_resolve_task_branch_adds_suffix_when_candidate_exists(monkeypatch) -> None:
    """New tasks should avoid colliding with existing publication branches."""
    task = _ResolvedTask("ship-it")
    monkeypatch.setattr(
        "developer.version_control.adapters.git_adapter.GitVersionControlAdapter.branch_exists",
        lambda self, repo_path, branch_name, remote_name="origin": True,
    )

    branch = _resolve_task_branch(
        Path("."),
        task,
        publication=None,
        version_control=GitVersionControlAdapter(),
    )

    assert branch.startswith("ship-it-")


def test_resolve_workspace_start_point_prefers_publication_branch() -> None:
    """Follow-up runs should start from the publication branch when present."""
    publication = TaskPublicationState(
        task_name="ship-it",
        task_path="/tmp/plan.md",
        branch_name="published-branch",
        base_branch="main",
        status="created",
    )

    start_point = _resolve_workspace_start_point(
        publication=publication,
        base_branch="main",
    )

    assert start_point == "published-branch"


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
