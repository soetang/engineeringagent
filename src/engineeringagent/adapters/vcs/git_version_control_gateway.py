"""Git-backed implementation of the version-control gateway port."""

from __future__ import annotations

import subprocess
from pathlib import Path

from engineeringagent.ports import (
    CommitRequest,
    CommitResult,
    DiffSummary,
    ResetRequest,
    ResetResult,
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

    def reset_hard(self, request: ResetRequest) -> ResetResult:
        """Reset the repository to one accepted revision and clean untracked files."""
        reset_proc = subprocess.run(
            ["git", "reset", "--hard", request.target_ref],
            cwd=request.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if reset_proc.returncode != 0:
            return ResetResult(
                reset_applied=False,
                head_commit=None,
                stdout=reset_proc.stdout or "",
                stderr=reset_proc.stderr or "",
                failure_stage="git_reset",
            )

        clean_stdout = ""
        clean_stderr = ""
        if request.clean_untracked:
            clean_proc = subprocess.run(
                ["git", "clean", "-fd"],
                cwd=request.project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            clean_stdout = clean_proc.stdout or ""
            clean_stderr = clean_proc.stderr or ""
            if clean_proc.returncode != 0:
                return ResetResult(
                    reset_applied=False,
                    head_commit=None,
                    stdout=(reset_proc.stdout or "") + clean_stdout,
                    stderr=(reset_proc.stderr or "") + clean_stderr,
                    failure_stage="git_clean",
                )

        return ResetResult(
            reset_applied=True,
            head_commit=self.head_commit(request.project_root),
            stdout=(reset_proc.stdout or "") + clean_stdout,
            stderr=(reset_proc.stderr or "") + clean_stderr,
            failure_stage=None,
        )
