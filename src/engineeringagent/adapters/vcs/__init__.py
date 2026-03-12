"""Version-control adapters."""

from .git_cli import ls_files, precommit_install
from .git_worktree_manager import GitWorktreeManager
from .git_version_control_gateway import GitCliVersionControlGateway

__all__ = [
    "GitWorktreeManager",
    "GitCliVersionControlGateway",
    "ls_files",
    "precommit_install",
]
