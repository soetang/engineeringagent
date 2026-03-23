"""Tests for workspace-backed implementation run orchestration."""

from developer.orchestrators.runs.implementation_workspace_run_orchestrator import (
    ImplementationWorkspaceRunOrchestrator,
)
from developer.orchestrators.runs.models import (
    ImplementationWorkspaceRunRequest,
    PublishedTaskBranch,
    WorkspaceRunResult,
)


class _FakeTask:
    def __init__(self, task_id: str = "ship-it", task_path: str | None = None) -> None:
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

    def get_branch_name(self) -> str:
        return "ship-it"


class _PublicationStore:
    def __init__(self, publication: PublishedTaskBranch | None) -> None:
        self.publication = publication
        self.calls: list[tuple[str, str | None]] = []

    def get_task_publication(
        self,
        task_name: str,
        task_path: str | None,
    ) -> PublishedTaskBranch | None:
        self.calls.append((task_name, task_path))
        return self.publication


class _BranchInspector:
    def __init__(self, *, current_branch: str = "main", branch_exists: bool = False):
        self.current_branch = current_branch
        self.branch_exists_result = branch_exists
        self.current_branch_calls: list[str] = []
        self.branch_exists_calls: list[tuple[str, str, str]] = []

    def get_current_branch(self, repo_path: str) -> str:
        self.current_branch_calls.append(repo_path)
        return self.current_branch

    def branch_exists(
        self,
        repo_path: str,
        branch_name: str,
        remote_name: str = "origin",
    ) -> bool:
        self.branch_exists_calls.append((repo_path, branch_name, remote_name))
        return self.branch_exists_result


class _WorkspaceRunner:
    def __init__(self) -> None:
        self.commands = []

    def run(self, command):
        self.commands.append(command)
        return WorkspaceRunResult(
            workspace_id="workspace-1",
            run_id="run-1",
            status="succeeded",
            latest_message="ok",
            metadata={
                "task_branch_name": command.workspace_metadata["task_branch_name"]
            },
        )


def _build_request(task: _FakeTask | None = None) -> ImplementationWorkspaceRunRequest:
    return ImplementationWorkspaceRunRequest(
        repo_path="/repo",
        task_input="docs/plans/ship-it.md",
        normalized_task_input="docs/plans/ship-it.md",
        task=task or _FakeTask(task_path="docs/plans/ship-it.md"),
        max_iterations=20,
    )


def test_reuses_publication_branch_for_task_branch_and_start_point() -> None:
    """Published tasks should keep using the published branch and start point."""
    publication_store = _PublicationStore(PublishedTaskBranch(branch_name="published"))
    branch_inspector = _BranchInspector(current_branch="main")
    workspace_runner = _WorkspaceRunner()
    orchestrator = ImplementationWorkspaceRunOrchestrator(
        publication_store=publication_store,
        branch_inspector=branch_inspector,
        workspace_runner=workspace_runner,
    )

    outcome = orchestrator.run(_build_request())

    assert outcome.status == "succeeded"
    assert publication_store.calls == [("Ship it", "docs/plans/ship-it.md")]
    assert branch_inspector.branch_exists_calls == []
    command = workspace_runner.commands[0]
    assert command.workspace_metadata["task_branch_name"] == "published"
    assert command.workspace_metadata["start_point"] == "published"
    assert command.run_context["task_branch_name"] == "published"


def test_adds_suffix_when_branch_candidate_already_exists() -> None:
    """New branches should gain a suffix when the stable name collides."""
    publication_store = _PublicationStore(None)
    branch_inspector = _BranchInspector(branch_exists=True)
    workspace_runner = _WorkspaceRunner()
    orchestrator = ImplementationWorkspaceRunOrchestrator(
        publication_store=publication_store,
        branch_inspector=branch_inspector,
        workspace_runner=workspace_runner,
    )

    orchestrator.run(_build_request())

    command = workspace_runner.commands[0]
    task_branch_name = command.workspace_metadata["task_branch_name"]
    assert task_branch_name.startswith("ship-it-")
    assert command.workspace_metadata["start_point"] == "main"
    assert command.run_context["task_branch_name"] == task_branch_name
    assert branch_inspector.branch_exists_calls == [("/repo", "ship-it", "origin")]


def test_builds_workspace_run_command_from_resolved_plan() -> None:
    """The runtime command should mirror the resolved workspace plan."""
    publication_store = _PublicationStore(None)
    branch_inspector = _BranchInspector(current_branch="develop", branch_exists=False)
    workspace_runner = _WorkspaceRunner()
    task = _FakeTask(task_id="task-123", task_path="docs/plans/ship-it.md")
    orchestrator = ImplementationWorkspaceRunOrchestrator(
        publication_store=publication_store,
        branch_inspector=branch_inspector,
        workspace_runner=workspace_runner,
    )

    outcome = orchestrator.run(_build_request(task))

    command = workspace_runner.commands[0]
    assert command.repo_path == "/repo"
    assert command.base_branch == "develop"
    assert command.task_id == "task-123"
    assert command.agent_kind == "implementation"
    assert command.workspace_metadata == {
        "task_id": "task-123",
        "task_name": "Ship it",
        "task_path": "docs/plans/ship-it.md",
        "task_branch_name": "ship-it",
        "remote_name": "origin",
        "start_point": "develop",
    }
    assert command.run_context == {
        "task_input": "docs/plans/ship-it.md",
        "task_id": "task-123",
        "task_name": "Ship it",
        "task_path": "docs/plans/ship-it.md",
        "task_branch_name": "ship-it",
        "max_iterations": 20,
    }
    assert outcome.metadata == {"task_branch_name": "ship-it"}
