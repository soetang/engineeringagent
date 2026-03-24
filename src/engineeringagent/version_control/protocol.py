"""Protocol boundaries for version control adapters."""

from typing import Protocol

from engineeringagent.orchestrators.publication.protocols import (
    PublicationVersionControlPort,
)


class VersionControlProtocol(PublicationVersionControlPort, Protocol):
    """Repository-local version control operations."""

    def get_head_sha(self, repo_path: str) -> str:
        """Return the current HEAD commit sha."""
        ...

    def get_current_branch(self, repo_path: str) -> str:
        """Return the currently checked out branch name."""
        ...

    def branch_exists(
        self,
        repo_path: str,
        branch_name: str,
        remote_name: str = "origin",
    ) -> bool:
        """Return whether a branch exists locally or remotely."""
        ...

    def ensure_clean_checkout(self, repo_path: str) -> None:
        """Fail when the repository contains tracked or untracked changes."""
        ...
