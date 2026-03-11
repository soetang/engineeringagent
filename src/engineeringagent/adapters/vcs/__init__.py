"""Version-control adapters."""

from .git_cli import ls_files, precommit_install
from .git_feature_workspace_manager import GitFeatureWorkspaceManager
from .git_version_control_gateway import GitCliVersionControlGateway

__all__ = [
    "GitFeatureWorkspaceManager",
    "GitCliVersionControlGateway",
    "ls_files",
    "precommit_install",
]
