"""Git-backed implementation of feature workspace reset lifecycle."""

from __future__ import annotations

import subprocess
from pathlib import Path

from engineeringagent.ports import (
    FeatureWorkspaceManager,
    WorkspaceResetRequest,
    WorkspaceResetResult,
)


class GitFeatureWorkspaceManager(FeatureWorkspaceManager):
    """Run git workspace reset commands for recovery workflows."""

    def reset_to_last_accepted(
        self,
        request: WorkspaceResetRequest,
    ) -> WorkspaceResetResult:
        """Reset the repository to one accepted revision and clean untracked files."""
        reset_proc = subprocess.run(
            ["git", "reset", "--hard", request.target_ref],
            cwd=request.project_root,
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
                cwd=request.project_root,
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
            head_commit=_head_commit(request.project_root),
            stdout=(reset_proc.stdout or "") + clean_stdout,
            stderr=(reset_proc.stderr or "") + clean_stderr,
            failure_stage=None,
        )


def _head_commit(project_root: Path) -> str | None:
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
