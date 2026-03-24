"""GitHub forge adapter using the gh CLI."""

import json
import subprocess

from engineeringagent.forge.models import PullRequestRequest, PullRequestResult


class GitHubForgeAdapter:
    """Perform GitHub publication operations through the gh CLI."""

    def find_open_pull_request(
        self,
        repo_path: str,
        branch_name: str,
        base_branch: str,
    ) -> PullRequestResult | None:
        """Return the open pull request for the given branch, if any."""
        result = self._run_gh(
            repo_path,
            "pr",
            "list",
            "--state",
            "open",
            "--head",
            branch_name,
            "--base",
            base_branch,
            "--json",
            "number,url,title,headRefName,baseRefName",
        )
        entries = json.loads(result.stdout)
        if not entries:
            return None
        return _to_pull_request_result(entries[0])

    def create_pull_request(
        self, repo_path: str, request: PullRequestRequest
    ) -> PullRequestResult:
        """Create a pull request and return the resulting metadata."""
        result = self._run_gh(
            repo_path,
            "pr",
            "create",
            "--title",
            request.title,
            "--body",
            request.body,
            "--head",
            request.head_branch,
            "--base",
            request.base_branch,
        )
        url = result.stdout.strip()
        number = url.rstrip("/").split("/")[-1]
        return PullRequestResult(
            number=number,
            url=url,
            title=request.title,
            head_branch=request.head_branch,
            base_branch=request.base_branch,
        )

    def validate_available(self, repo_path: str) -> None:
        """Validate gh installation and repository access."""
        self._run_gh(repo_path, "repo", "view")

    def _run_gh(self, repo_path: str, *args: str) -> subprocess.CompletedProcess[str]:
        """Run one gh command and surface actionable errors."""
        try:
            return subprocess.run(
                ["gh", *args],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "gh CLI is required when forge publication is enabled"
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip() or "gh command failed"
            raise ValueError(stderr) from exc


def _to_pull_request_result(payload: dict[str, object]) -> PullRequestResult:
    """Convert one gh JSON payload into the shared model."""
    return PullRequestResult(
        number=str(payload["number"]),
        url=str(payload["url"]),
        title=str(payload["title"]),
        head_branch=str(payload["headRefName"]),
        base_branch=str(payload["baseRefName"]),
    )
