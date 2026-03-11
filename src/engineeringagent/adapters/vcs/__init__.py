"""Version-control adapters."""

from .git_cli import add_all, commit, diff_name_status, head_short, ls_files, precommit_install, status_porcelain

__all__ = [
    "add_all",
    "commit",
    "diff_name_status",
    "head_short",
    "ls_files",
    "precommit_install",
    "status_porcelain",
]
