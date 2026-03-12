"""Git-backed implementation of worktree reset lifecycle."""

from __future__ import annotations

import subprocess
from pathlib import Path

from engineeringagent.ports import (
    FeatureWorkspaceManager,
    WorkspaceState,
    WorkspaceResetRequest,
    WorkspaceResetResult,
)


class GitWorktreeManager(FeatureWorkspaceManager):
    """Run git workspace reset commands for recovery workflows."""

    def get_state(self, workspace_path: Path) -> WorkspaceState:
        """Return normalized git status information for one workspace."""
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or "git status failed")

        changed_paths: list[str] = []
        has_untracked_files = False
        for line in (proc.stdout or "").splitlines():
            if not line:
                continue
            status_code = line[:2]
            raw_path = line[3:] if len(line) > 3 else ""
            normalized_path = _normalize_status_path(raw_path)
            if normalized_path:
                changed_paths.append(normalized_path)
            if "?" in status_code:
                has_untracked_files = True

        return WorkspaceState(
            clean=not changed_paths,
            changed_paths=tuple(changed_paths),
            has_untracked_files=has_untracked_files,
        )

    def reset_to_last_accepted(
        self,
        request: WorkspaceResetRequest,
    ) -> WorkspaceResetResult:
        """Reset the repository to one accepted revision and clean untracked files."""
        reset_proc = subprocess.run(
            ["git", "reset", "--hard", request.target_ref],
            cwd=request.workspace_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if reset_proc.returncode != 0:
            return WorkspaceResetResult(
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
                cwd=request.workspace_path,
                capture_output=True,
                text=True,
                check=False,
            )
            clean_stdout = clean_proc.stdout or ""
            clean_stderr = clean_proc.stderr or ""
            if clean_proc.returncode != 0:
                return WorkspaceResetResult(
                    reset_applied=False,
                    head_commit=None,
                    stdout=(reset_proc.stdout or "") + clean_stdout,
                    stderr=(reset_proc.stderr or "") + clean_stderr,
                    failure_stage="git_clean",
                )

        return WorkspaceResetResult(
            reset_applied=True,
            head_commit=_head_commit(request.workspace_path),
            stdout=(reset_proc.stdout or "") + clean_stdout,
            stderr=(reset_proc.stderr or "") + clean_stderr,
            failure_stage=None,
        )


def _head_commit(workspace_path: Path) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=workspace_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None


def _normalize_status_path(raw_path: str) -> str:
    path = raw_path.strip()
    if " -> " in path:
        _, _, path = path.partition(" -> ")
    return path
