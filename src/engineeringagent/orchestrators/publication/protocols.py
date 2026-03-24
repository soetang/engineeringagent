"""Protocol interfaces for publication orchestration dependencies."""

from collections.abc import Mapping
from typing import Protocol

from .models import (
    CommitMessageContext,
    CommitRequest,
    CommitResult,
    GitIdentity,
    PublicationState,
    PullRequestContentContext,
    PullRequestRequest,
    PullRequestResult,
    PushResult,
    WorkingTreeStatus,
)


class PublicationVersionControlPort(Protocol):
    """Repository-local operations needed by publication orchestration."""

    def validate_repository(self, repo_path: str) -> None:
        """Validate that the path points at a git repository."""
        ...

    def get_status(self, repo_path: str) -> WorkingTreeStatus:
        """Return structured repository status."""
        ...

    def has_changes(self, repo_path: str) -> bool:
        """Return whether the repository has any changes."""
        ...

    def stage_all(self, repo_path: str) -> None:
        """Stage tracked and untracked changes."""
        ...

    def resolve_identity(self, repo_path: str) -> GitIdentity:
        """Resolve commit author identity for the repository."""
        ...

    def create_commit(self, repo_path: str, request: CommitRequest) -> CommitResult:
        """Create one commit in the repository."""
        ...

    def push_branch(
        self,
        repo_path: str,
        branch_name: str,
        remote_name: str,
        source_ref: str = "HEAD",
    ) -> PushResult:
        """Push one ref to a remote branch."""
        ...

    def get_diff(self, repo_path: str, staged: bool = False) -> str:
        """Return a text diff for the repository."""
        ...

    def get_recent_commits(self, repo_path: str, limit: int = 5) -> str:
        """Return recent commit summaries."""
        ...


class PublicationForgePort(Protocol):
    """Forge-hosting operations needed by publication orchestration."""

    def validate_available(self, repo_path: str) -> None:
        """Validate that the forge CLI is installed and usable."""
        ...

    def find_open_pull_request(
        self,
        repo_path: str,
        branch_name: str,
        base_branch: str,
    ) -> PullRequestResult | None:
        """Return one open pull request for the requested branch, if any."""
        ...

    def create_pull_request(
        self,
        repo_path: str,
        request: PullRequestRequest,
    ) -> PullRequestResult:
        """Create a new pull request."""
        ...


class PublicationPromptRenderer(Protocol):
    """Render publication prompts from typed domain context."""

    def render_commit_prompt(self, context: CommitMessageContext) -> str:
        """Render the commit prompt for one publication event."""
        ...

    def render_pull_request_prompt(self, context: PullRequestContentContext) -> str:
        """Render the pull-request prompt for one publication event."""
        ...


class PublicationStateStore(Protocol):
    """Persist publication state for one task."""

    def save_publication(self, publication: PublicationState) -> None:
        """Persist the latest publication state."""
        ...


class RunMetadataStore(Protocol):
    """Persist metadata updates for one orchestrated run."""

    def update_run_metadata(self, run_id: str, updates: Mapping[str, object]) -> None:
        """Merge metadata updates into the stored run."""
        ...

    def append_run_metadata_item(self, run_id: str, key: str, value: object) -> None:
        """Append a single metadata item for the stored run."""
        ...


class WorkspaceLifecyclePort(Protocol):
    """Cleanup operations needed after publication completes."""

    def destroy_workspace(self, workspace_id: str) -> None:
        """Destroy one workspace by identifier."""
        ...
