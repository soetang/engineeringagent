"""Git-backed implementation of the version-control gateway port."""

from __future__ import annotations

import subprocess
from pathlib import Path

from engineeringagent.ports import (
    CommitRequest,
    CommitResult,
    DiffSummary,
    VersionControlFailure,
    WorktreeStatus,
)


class GitCliVersionControlGateway:
    """Run normalized git commands for orchestration consumers."""

    def diff_against_base(
        self,
        project_root: Path,
        *,
        base_ref: str | None = None,
        head_ref: str | None = None,
    ) -> DiffSummary:
        """Return raw `git diff --name-status` output for downstream parsing."""
        command = [
            "git",
            "diff",
            "--name-status",
            "--find-renames",
            "--diff-filter=AMDR",
        ]
        if base_ref is not None:
            command.append(base_ref)
        if head_ref is not None:
            command.append(head_ref)

        proc = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip() or "git diff failed"
            raise VersionControlFailure(detail)

        return DiffSummary(
            base_ref=base_ref,
            head_ref=head_ref,
            summary_text=proc.stdout or "",
        )

    def head_commit(self, project_root: Path) -> str | None:
        """Return the short head commit hash when git can resolve it."""
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return None
        return (proc.stdout or "").strip() or None

    def worktree_status(self, project_root: Path) -> WorktreeStatus:
        """Return normalized dirty-state information for the current repository."""
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip() or "git status failed"
            raise VersionControlFailure(detail)
        stdout = proc.stdout or ""
        return WorktreeStatus(
            dirty=bool(stdout.strip()),
            stdout=stdout,
            stderr=proc.stderr or "",
        )

    def commit(self, request: CommitRequest) -> CommitResult:
        """Stage and commit changes using the deterministic local identity."""
        if request.stage_all:
            add_proc = subprocess.run(
                ["git", "add", "-A", "--", "."],
                cwd=request.project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if add_proc.returncode != 0:
                return CommitResult(
                    commit_created=False,
                    commit_sha=None,
                    stdout=add_proc.stdout or "",
                    stderr=add_proc.stderr or "",
                    failure_stage="git_add",
                )

        command = [
            "git",
            "-c",
            "user.name=engineeringagent",
            "-c",
            "user.email=engineeringagent@local",
            "commit",
            "-m",
            request.message,
        ]
        if request.allow_empty:
            command.append("--allow-empty")

        commit_proc = subprocess.run(
            command,
            cwd=request.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if commit_proc.returncode != 0:
            return CommitResult(
                commit_created=False,
                commit_sha=None,
                stdout=commit_proc.stdout or "",
                stderr=commit_proc.stderr or "",
                failure_stage="git_commit",
            )

        return CommitResult(
            commit_created=True,
            commit_sha=self.head_commit(request.project_root),
            stdout=commit_proc.stdout or "",
            stderr=commit_proc.stderr or "",
            failure_stage=None,
        )
