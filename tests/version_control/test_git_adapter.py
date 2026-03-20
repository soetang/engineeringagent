"""Tests for the git version control adapter."""

import os
import subprocess
from pathlib import Path

from developer.version_control.adapters.git_adapter import GitVersionControlAdapter
from developer.version_control.models import CommitRequest


def _git_env() -> dict[str, str]:
    """Return git author env suitable for temporary test commits."""
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test User",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test User",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return env


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command for a temporary repository."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=_git_env(),
    )


def _init_repo(repo: Path) -> None:
    """Create a small repository with one commit on main."""
    repo.mkdir(parents=True)
    _run_git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("start\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-m", "initial")


def test_git_adapter_reports_no_changes_for_clean_repo(tmp_path) -> None:
    """A clean repo should not produce commits or changed status entries."""
    repo = tmp_path / "repo"
    _init_repo(repo)

    adapter = GitVersionControlAdapter()

    assert adapter.has_changes(str(repo)) is False
    assert adapter.get_status(str(repo)).tracked_changes == []
    assert adapter.get_status(str(repo)).untracked_files == []


def test_git_adapter_creates_commit_with_explicit_identity(tmp_path) -> None:
    """Commits should use per-command author identity, not repo config changes."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("updated\n", encoding="utf-8")

    adapter = GitVersionControlAdapter()
    adapter.stage_all(str(repo))
    result = adapter.create_commit(
        str(repo),
        CommitRequest(
            subject="Add version control",
            body="",
            author_name="Automation Bot",
            author_email="bot@example.com",
        ),
    )

    author = _run_git(repo, "log", "-1", "--pretty=format:%an <%ae>").stdout

    assert result.subject == "Add version control"
    assert len(result.sha) == 40
    assert author == "Automation Bot <bot@example.com>"


def test_git_adapter_pushes_head_to_publication_branch(tmp_path) -> None:
    """Pushes should target the publication branch name."""
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
    )
    _init_repo(repo)
    _run_git(repo, "remote", "add", "origin", str(remote))

    adapter = GitVersionControlAdapter()
    push = adapter.push_branch(str(repo), "publication-branch", "origin")
    remote_refs = _run_git(
        repo, "ls-remote", "--heads", "origin", "publication-branch"
    ).stdout

    assert push.branch_name == "publication-branch"
    assert "publication-branch" in remote_refs
