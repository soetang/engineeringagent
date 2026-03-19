"""Workspace configuration models."""

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceSettings(BaseModel):
    """Configuration for local workspace orchestration."""

    default_provider: str = Field(default="git_worktree")
    state_dir: str = Field(default=".developer/state")
    git_worktree_root_dir: str = Field(default="developer-workspaces")

    model_config = ConfigDict(extra="forbid")
