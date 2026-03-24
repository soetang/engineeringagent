"""Tests for publication models and protocol-shaped contracts."""

from engineeringagent.orchestrators.loop.models import RunPublicationResult
from engineeringagent.orchestrators.publication import (
    CommitMessage,
    CommitMessageContext,
    PublicationPromptRenderer,
    PublicationState,
    PublicationVersionControlPort,
    PullRequestContentContext,
)


def test_commit_message_context_exposes_publication_inputs() -> None:
    """Commit message context should keep publication-owned prompt inputs together."""
    context = CommitMessageContext(
        repo_path="/tmp/repo",
        task_name="task",
        task_path="docs/task.md",
        task_branch_name="task-branch",
        base_branch="main",
        latest_change_summary="Added publication ports",
        staged_diff="diff --git a",
        recent_commits="abc123 previous",
    )

    assert context.repo_path == "/tmp/repo"
    assert context.staged_diff == "diff --git a"
    assert context.recent_commits == "abc123 previous"


def test_pull_request_content_context_defaults_optional_text_inputs() -> None:
    """Pull-request context should provide empty text defaults for generators."""
    context = PullRequestContentContext(
        repo_path="/tmp/repo",
        task_name="task",
        task_branch_name="task-branch",
        base_branch="main",
    )

    assert context.diff == ""
    assert context.recent_commits == ""
    assert context.latest_change_summary is None


def test_publication_run_result_keeps_optional_links_explicit() -> None:
    """Publication results should still carry branch and link details explicitly."""
    result = RunPublicationResult(
        branch_name="task-branch", message="branch=task-branch"
    )

    assert result.branch_name == "task-branch"
    assert result.pr_url is None


def test_publication_state_tracks_task_specific_publication_data() -> None:
    """Publication state should keep publication persistence in the domain layer."""
    state = PublicationState(
        task_name="task",
        task_path="docs/task.md",
        branch_name="task-branch",
        base_branch="main",
        status="created",
    )

    assert state.task_name == "task"
    assert state.status == "created"


def test_publication_protocols_are_structurally_implementable() -> None:
    """Publication ports should be satisfied structurally without infra imports."""

    class StubVersionControl:
        def validate_repository(self, repo_path: str) -> None:
            del repo_path

        def get_status(self, repo_path: str):
            del repo_path
            raise NotImplementedError

        def has_changes(self, repo_path: str) -> bool:
            del repo_path
            return False

        def stage_all(self, repo_path: str) -> None:
            del repo_path

        def resolve_identity(self, repo_path: str):
            del repo_path
            raise NotImplementedError

        def create_commit(self, repo_path: str, request):
            del repo_path, request
            raise NotImplementedError

        def push_branch(
            self,
            repo_path: str,
            branch_name: str,
            remote_name: str,
            source_ref: str = "HEAD",
        ):
            del repo_path, branch_name, remote_name, source_ref
            raise NotImplementedError

        def get_diff(self, repo_path: str, staged: bool = False) -> str:
            del repo_path, staged
            return ""

        def get_recent_commits(self, repo_path: str, limit: int = 5) -> str:
            del repo_path, limit
            return ""

    port: PublicationVersionControlPort = StubVersionControl()
    message = CommitMessage(subject="feat: add publication models")

    assert isinstance(port, StubVersionControl)
    assert message.subject == "feat: add publication models"


def test_publication_prompt_renderer_protocol_is_structurally_implementable() -> None:
    """Publication prompt rendering should remain a narrow structural contract."""

    class StubPromptRenderer:
        def render_commit_prompt(self, context: CommitMessageContext) -> str:
            return context.task_name

        def render_pull_request_prompt(self, context: PullRequestContentContext) -> str:
            return context.task_name

    prompt_renderer: PublicationPromptRenderer = StubPromptRenderer()

    assert (
        prompt_renderer.render_commit_prompt(
            CommitMessageContext(
                repo_path="/tmp/repo",
                task_name="task",
                task_branch_name="task-branch",
                base_branch="main",
            )
        )
        == "task"
    )
