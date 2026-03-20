"""Git-backed version control adapter."""

import os
import subprocess
import tempfile
from pathlib import Path

from developer.version_control.models import (
    CommitRequest,
    CommitResult,
    GitIdentity,
    PushResult,
    WorkingTreeStatus,
)
from developer.version_control.settings import VersionControlSettings


class GitVersionControlAdapter:
    """Perform repository operations through the git CLI."""

    def __init__(self, settings: VersionControlSettings | None = None) -> None:
        """Store optional identity overrides from configuration."""
        self._settings = settings or VersionControlSettings()

    def get_status(self, repo_path: str) -> WorkingTreeStatus:
        """Return structured working tree status."""
        result = self._run_git(repo_path, "status", "--short")
        tracked_changes: list[str] = []
        untracked_files: list[str] = []
        for line in result.stdout.splitlines():
            if not line:
                continue
            path = line[3:]
            if line.startswith("??"):
                untracked_files.append(path)
            else:
                tracked_changes.append(path)
        return WorkingTreeStatus(
            tracked_changes=tracked_changes,
            untracked_files=untracked_files,
        )

    def has_changes(self, repo_path: str) -> bool:
        """Return whether the repository contains tracked or untracked changes."""
        status = self.get_status(repo_path)
        return bool(status.tracked_changes or status.untracked_files)

    def stage_all(self, repo_path: str) -> None:
        """Stage tracked and untracked changes."""
        self._run_git(repo_path, "add", "--all")

    def create_commit(self, repo_path: str, request: CommitRequest) -> CommitResult:
        """Create one commit using per-command author identity."""
        commit_message = request.subject.strip()
        body = request.body.strip()
        if body:
            commit_message = f"{commit_message}\n\n{body}"

        env = self._git_identity_env(request)
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(commit_message)
            message_path = fh.name

        try:
            self._run_git(repo_path, "commit", "--file", message_path, env=env)
        finally:
            Path(message_path).unlink(missing_ok=True)
        return CommitResult(sha=self.get_head_sha(repo_path), subject=request.subject)

    def get_head_sha(self, repo_path: str) -> str:
        """Return the current HEAD commit sha."""
        return self._run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    def push_branch(
        self,
        repo_path: str,
        branch_name: str,
        remote_name: str,
        source_ref: str = "HEAD",
    ) -> PushResult:
        """Push one source ref to one remote branch without force."""
        self._run_git(
            repo_path,
            "push",
            remote_name,
            f"{source_ref}:refs/heads/{branch_name}",
        )
        return PushResult(
            branch_name=branch_name,
            remote_name=remote_name,
            source_ref=source_ref,
        )

    def resolve_identity(self, repo_path: str) -> GitIdentity:
        """Resolve git identity, preferring explicit config overrides."""
        if self._settings.author_name and self._settings.author_email:
            return GitIdentity(
                name=self._settings.author_name,
                email=self._settings.author_email,
            )
        name = self._run_git(repo_path, "config", "user.name").stdout.strip()
        email = self._run_git(repo_path, "config", "user.email").stdout.strip()
        if not name or not email:
            raise ValueError(
                "Git user identity is required for automated commits. Set git user.name and user.email or configure [version_control] author_name/author_email."
            )
        return GitIdentity(
            name=self._settings.author_name or name,
            email=self._settings.author_email or email,
        )

    def branch_exists(self, repo_path: str, branch_name: str) -> bool:
        """Return whether a branch exists locally or on origin."""
        local = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if local.returncode == 0:
            return True
        remote = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch_name],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        return remote.returncode == 0 and bool(remote.stdout.strip())

    def get_diff(self, repo_path: str, staged: bool = False) -> str:
        """Return a git diff for the repository."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        return self._run_git(repo_path, *args).stdout.strip()

    def get_recent_commits(self, repo_path: str, limit: int = 5) -> str:
        """Return recent commit subjects and shas."""
        return self._run_git(
            repo_path,
            "log",
            f"--max-count={limit}",
            "--pretty=format:%h %s",
        ).stdout.strip()

    def validate_repository(self, repo_path: str) -> None:
        """Validate that the given path is a git repository."""
        self._run_git(repo_path, "rev-parse", "--is-inside-work-tree")

    def _git_identity_env(self, request: CommitRequest) -> dict[str, str]:
        """Build a subprocess environment for git author identity."""
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": request.author_name,
                "GIT_AUTHOR_EMAIL": request.author_email,
                "GIT_COMMITTER_NAME": request.author_name,
                "GIT_COMMITTER_EMAIL": request.author_email,
            }
        )
        return env

    def _run_git(
        self,
        repo_path: str,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run one git command and convert stderr into a ValueError."""
        try:
            return subprocess.run(
                ["git", *args],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip() or "git command failed"
            raise ValueError(stderr) from exc
