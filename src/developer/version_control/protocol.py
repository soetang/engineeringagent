"""Protocol boundaries for version control adapters."""

from typing import Protocol

from developer.version_control.models import (
    CommitRequest,
    CommitResult,
    GitIdentity,
    PushResult,
    WorkingTreeStatus,
)


class VersionControlProtocol(Protocol):
    """Repository-local version control operations."""

    def get_status(self, repo_path: str) -> WorkingTreeStatus:
        """Return structured repository status."""
        ...

    def has_changes(self, repo_path: str) -> bool:
        """Return whether the repository has any changes."""
        ...

    def stage_all(self, repo_path: str) -> None:
        """Stage tracked and untracked changes."""
        ...

    def create_commit(self, repo_path: str, request: CommitRequest) -> CommitResult:
        """Create one commit in the repository."""
        ...

    def get_head_sha(self, repo_path: str) -> str:
        """Return the current HEAD commit sha."""
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

    def resolve_identity(self, repo_path: str) -> GitIdentity:
        """Resolve commit author identity for the repository."""
        ...

    def branch_exists(self, repo_path: str, branch_name: str) -> bool:
        """Return whether a branch exists locally or remotely."""
        ...

    def get_diff(self, repo_path: str, staged: bool = False) -> str:
        """Return a text diff for the repository."""
        ...

    def get_recent_commits(self, repo_path: str, limit: int = 5) -> str:
        """Return recent commit summaries."""
        ...

    def validate_repository(self, repo_path: str) -> None:
        """Validate that the path points at a git repository."""
        ...
