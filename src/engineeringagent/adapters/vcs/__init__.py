"""Version-control adapters."""

from .git_cli import ls_files, precommit_install, status_porcelain
from .git_version_control_gateway import GitCliVersionControlGateway

__all__ = [
    "GitCliVersionControlGateway",
    "ls_files",
    "precommit_install",
    "status_porcelain",
]
