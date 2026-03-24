"""Protocol boundaries for forge adapters."""

from typing import Protocol

from engineeringagent.forge.models import PullRequestRequest, PullRequestResult


class ForgeProtocol(Protocol):
    """Hosting platform operations for publication."""

    def find_open_pull_request(
        self,
        repo_path: str,
        branch_name: str,
        base_branch: str,
    ) -> PullRequestResult | None:
        """Return one open pull request for the requested branch, if any."""
        ...

    def create_pull_request(
        self, repo_path: str, request: PullRequestRequest
    ) -> PullRequestResult:
        """Create a new pull request."""
        ...

    def validate_available(self, repo_path: str) -> None:
        """Validate that the forge CLI is installed and usable."""
        ...
