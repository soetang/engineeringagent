"""Unit tests for publication orchestration workflow decisions."""

from datetime import UTC, datetime

from engineeringagent.orchestrators.loop.models import (
    AgentResult,
    ImplementationContext,
)
from engineeringagent.orchestrators.publication import (
    CommitMessage,
    CommitMessageContext,
    CommitRequest,
    CommitResult,
    GitIdentity,
    PublicationObserver,
    PublicationState,
    PullRequestContent,
    PullRequestContentContext,
    PullRequestRequest,
    PullRequestResult,
    PushResult,
)
from engineeringagent.workspaces.models import RunHandle, RunStatus


class _FakePublicationStateStore:
    def __init__(self) -> None:
        self.publications: list[PublicationState] = []

    def save_publication(self, publication: PublicationState) -> None:
        self.publications.append(publication)


class _FakeRunMetadataStore:
    def __init__(self) -> None:
        self.runs: dict[str, RunHandle] = {}

    def save_run(self, run: RunHandle) -> None:
        self.runs[run.id] = run

    def get_run(self, run_id: str) -> RunHandle:
        return self.runs[run_id]

    def update_run_metadata(self, run_id: str, updates) -> None:
        run = self.get_run(run_id)
        metadata = dict(run.metadata)
        metadata.update(dict(updates))
        self.save_run(run.model_copy(update={"metadata": metadata}))

    def append_run_metadata_item(self, run_id: str, key: str, value: object) -> None:
        run = self.get_run(run_id)
        metadata = dict(run.metadata)
        existing = metadata.get(key, [])
        metadata[key] = [*existing, value] if isinstance(existing, list) else [value]
        self.save_run(run.model_copy(update={"metadata": metadata}))


class _FakeWorkspaceLifecycle:
    def __init__(self) -> None:
        self.destroyed: list[str] = []

    def destroy_workspace(self, workspace_id: str) -> None:
        self.destroyed.append(workspace_id)


class _ExplodingWorkspaceLifecycle:
    def destroy_workspace(self, workspace_id: str) -> None:
        del workspace_id
        raise RuntimeError("boom")


class _FakeVersionControl:
    def __init__(self, *, has_changes: bool = True) -> None:
        self.has_changes_value = has_changes
        self.staged_paths: list[str] = []
        self.commit_requests: list[CommitRequest] = []
        self.push_calls: list[tuple[str, str, str, str]] = []
        self.diff_calls: list[tuple[str, bool]] = []

    def validate_repository(self, repo_path: str) -> None:
        del repo_path

    def get_status(self, repo_path: str):
        del repo_path
        raise NotImplementedError

    def has_changes(self, repo_path: str) -> bool:
        del repo_path
        return self.has_changes_value

    def stage_all(self, repo_path: str) -> None:
        self.staged_paths.append(repo_path)

    def resolve_identity(self, repo_path: str) -> GitIdentity:
        del repo_path
        return GitIdentity(name="Dev", email="dev@example.com")

    def create_commit(self, repo_path: str, request: CommitRequest) -> CommitResult:
        del repo_path
        self.commit_requests.append(request)
        return CommitResult(sha="abc123", subject=request.subject)

    def push_branch(
        self,
        repo_path: str,
        branch_name: str,
        remote_name: str,
        source_ref: str = "HEAD",
    ) -> PushResult:
        self.push_calls.append((repo_path, branch_name, remote_name, source_ref))
        return PushResult(
            branch_name=branch_name,
            remote_name=remote_name,
            source_ref=source_ref,
        )

    def get_diff(self, repo_path: str, staged: bool = False) -> str:
        self.diff_calls.append((repo_path, staged))
        return "diff --git a/file.py"

    def get_recent_commits(self, repo_path: str, limit: int = 5) -> str:
        del repo_path, limit
        return "old123 previous commit"


class _StubPromptRenderer:
    def __init__(self) -> None:
        self.commit_contexts: list[CommitMessageContext] = []
        self.pull_request_contexts: list[PullRequestContentContext] = []

    def render_commit_prompt(self, context: CommitMessageContext) -> str:
        self.commit_contexts.append(context)
        return f"commit:{context.task_name}"

    def render_pull_request_prompt(self, context: PullRequestContentContext) -> str:
        self.pull_request_contexts.append(context)
        return f"pr:{context.task_name}"


class _StubAgentRunner:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def run_agent(self, prompt: str, output_format=None):
        del output_format
        self.prompts.append(prompt)
        if prompt.startswith("commit:"):
            return CommitMessage(subject="feat: publish", body="")
        return PullRequestContent(
            title="Ship publication boundary",
            summary=["Move publication orchestration into orchestrators."],
            body="## Summary\n- Move publication orchestration into orchestrators.",
        )


class _ExplodingAgentRunner:
    def run_agent(self, prompt: str, output_format=None):
        del prompt, output_format
        raise RuntimeError("boom")


class _FakeForge:
    def __init__(self, existing_pr: PullRequestResult | None = None) -> None:
        self.existing_pr = existing_pr
        self.find_calls: list[tuple[str, str, str]] = []
        self.create_requests: list[PullRequestRequest] = []

    def validate_available(self, repo_path: str) -> None:
        del repo_path

    def find_open_pull_request(
        self,
        repo_path: str,
        branch_name: str,
        base_branch: str,
    ) -> PullRequestResult | None:
        self.find_calls.append((repo_path, branch_name, base_branch))
        return self.existing_pr

    def create_pull_request(
        self,
        repo_path: str,
        request: PullRequestRequest,
    ) -> PullRequestResult:
        del repo_path
        self.create_requests.append(request)
        return PullRequestResult(
            number="42",
            url="https://example.test/pr/42",
            title=request.title,
            head_branch=request.head_branch,
            base_branch=request.base_branch,
        )


def _run_handle(run_id: str = "run-1") -> RunHandle:
    return RunHandle(
        id=run_id,
        workspace_id="ws-1",
        status=RunStatus.RUNNING,
        agent_kind="developer",
        started_at=datetime.now(UTC),
        metadata={},
    )


def _context() -> ImplementationContext:
    return ImplementationContext(
        workspace_id="ws-1",
        run_id="run-1",
        repo_path="/repo",
        workspace_path="/repo",
        task_branch_name="task-branch",
        base_branch="main",
        task_name="publication-boundary",
        task_path="docs/plans/publication-orchestration-boundary-plan.md",
    )


def test_on_iteration_passed_skips_commit_when_workspace_has_no_changes() -> None:
    """Passing iterations should skip staging and commit creation without changes."""
    run_metadata_store = _FakeRunMetadataStore()
    run_metadata_store.save_run(_run_handle())
    version_control = _FakeVersionControl(has_changes=False)
    observer = PublicationObserver(
        publication_state_store=_FakePublicationStateStore(),
        run_metadata_store=run_metadata_store,
        workspace_lifecycle=_FakeWorkspaceLifecycle(),
        version_control=version_control,
    )

    artifact = observer.on_iteration_passed(1, _context(), AgentResult(summary="done"))

    assert artifact is None
    assert version_control.staged_paths == []
    assert version_control.commit_requests == []
    assert run_metadata_store.get_run("run-1").metadata == {}


def test_on_iteration_passed_uses_fallback_commit_generator_when_primary_fails() -> (
    None
):
    """Passing iterations should still commit when fallback generation is needed."""
    run_metadata_store = _FakeRunMetadataStore()
    run_metadata_store.save_run(_run_handle())
    version_control = _FakeVersionControl()
    prompt_renderer = _StubPromptRenderer()
    observer = PublicationObserver(
        publication_state_store=_FakePublicationStateStore(),
        run_metadata_store=run_metadata_store,
        workspace_lifecycle=_FakeWorkspaceLifecycle(),
        version_control=version_control,
        prompt_renderer=prompt_renderer,
        agent_runner=_ExplodingAgentRunner(),
    )

    artifact = observer.on_iteration_passed(1, _context(), AgentResult(summary="done"))

    assert artifact is not None
    assert artifact.commit_subject == "chore: implement publication-boundary"
    assert version_control.commit_requests[0].subject == artifact.commit_subject
    assert prompt_renderer.commit_contexts[0].task_name == "publication-boundary"
    assert run_metadata_store.get_run("run-1").metadata["commit_message_subjects"] == [
        "chore: implement publication-boundary"
    ]


def test_on_run_succeeded_pushes_branch_and_skips_pr_when_forge_disabled() -> None:
    """Successful runs should push and clean up without invoking forge logic."""
    publication_state_store = _FakePublicationStateStore()
    run_metadata_store = _FakeRunMetadataStore()
    run_metadata_store.save_run(_run_handle())
    workspace_lifecycle = _FakeWorkspaceLifecycle()
    version_control = _FakeVersionControl()
    observer = PublicationObserver(
        publication_state_store=publication_state_store,
        run_metadata_store=run_metadata_store,
        workspace_lifecycle=workspace_lifecycle,
        version_control=version_control,
    )

    result = observer.on_run_succeeded(_context())

    assert result is not None
    assert result.branch_name == "task-branch"
    assert result.pr_url is None
    assert result.message == "branch=task-branch"
    assert version_control.push_calls == [("/repo", "task-branch", "origin", "HEAD")]
    assert publication_state_store.publications[-1].status == "pushed"
    assert run_metadata_store.get_run("run-1").metadata["forge_enabled"] is False
    assert workspace_lifecycle.destroyed == ["ws-1"]


def test_on_run_succeeded_reuses_open_pull_request() -> None:
    """Successful runs should reuse an open pull request when one already exists."""
    publication_state_store = _FakePublicationStateStore()
    run_metadata_store = _FakeRunMetadataStore()
    run_metadata_store.save_run(_run_handle())
    forge = _FakeForge(
        existing_pr=PullRequestResult(
            number="12",
            url="https://example.test/pr/12",
            title="Existing PR",
            head_branch="task-branch",
            base_branch="main",
        )
    )
    observer = PublicationObserver(
        publication_state_store=publication_state_store,
        run_metadata_store=run_metadata_store,
        workspace_lifecycle=_FakeWorkspaceLifecycle(),
        version_control=_FakeVersionControl(),
        forge=forge,
    )

    result = observer.on_run_succeeded(_context())

    assert result is not None
    assert result.pr_url == "https://example.test/pr/12"
    assert result.message == "Pull request updated: https://example.test/pr/12"
    assert forge.create_requests == []
    assert publication_state_store.publications[-1].status == "updated"
    assert run_metadata_store.get_run("run-1").metadata["publication_status"] == (
        "updated"
    )


def test_on_run_succeeded_creates_pull_request_when_none_exists() -> None:
    """Successful runs should generate and create a pull request when needed."""
    publication_state_store = _FakePublicationStateStore()
    run_metadata_store = _FakeRunMetadataStore()
    run_metadata_store.save_run(_run_handle())
    forge = _FakeForge()
    prompt_renderer = _StubPromptRenderer()
    agent_runner = _StubAgentRunner()
    observer = PublicationObserver(
        publication_state_store=publication_state_store,
        run_metadata_store=run_metadata_store,
        workspace_lifecycle=_FakeWorkspaceLifecycle(),
        version_control=_FakeVersionControl(),
        prompt_renderer=prompt_renderer,
        agent_runner=agent_runner,
        forge=forge,
    )

    result = observer.on_run_succeeded(_context())

    assert result is not None
    assert result.pr_url == "https://example.test/pr/42"
    assert result.message == "Pull request: https://example.test/pr/42"
    assert len(prompt_renderer.pull_request_contexts) == 1
    assert agent_runner.prompts[-1] == "pr:publication-boundary"
    assert forge.create_requests[0].title == "Ship publication boundary"
    assert publication_state_store.publications[-1].status == "created"
    assert run_metadata_store.get_run("run-1").metadata["pull_request_title"] == (
        "Ship publication boundary"
    )


def test_on_run_failed_records_failure_feedback() -> None:
    """Failed runs should record failure feedback on the run metadata."""
    run_metadata_store = _FakeRunMetadataStore()
    run_metadata_store.save_run(_run_handle())
    observer = PublicationObserver(
        publication_state_store=_FakePublicationStateStore(),
        run_metadata_store=run_metadata_store,
        workspace_lifecycle=_FakeWorkspaceLifecycle(),
        version_control=_FakeVersionControl(),
    )

    observer.on_run_failed(_context(), "gate failed")

    assert run_metadata_store.get_run("run-1").metadata == {
        "publication_status": "failed",
        "failure_feedback": "gate failed",
    }


def test_cleanup_failure_records_warning() -> None:
    """Cleanup failures should be converted into metadata warnings."""
    run_metadata_store = _FakeRunMetadataStore()
    run_metadata_store.save_run(_run_handle())
    observer = PublicationObserver(
        publication_state_store=_FakePublicationStateStore(),
        run_metadata_store=run_metadata_store,
        workspace_lifecycle=_ExplodingWorkspaceLifecycle(),
        version_control=_FakeVersionControl(),
    )

    observer.on_run_succeeded(_context())

    assert run_metadata_store.get_run("run-1").metadata["cleanup_warning"] == (
        "Workspace cleanup failed after publication"
    )
