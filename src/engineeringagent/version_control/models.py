"""Domain models for repository version control operations."""

from pydantic import BaseModel, ConfigDict, Field


class WorkingTreeStatus(BaseModel):
    """Structured working tree status."""

    model_config = ConfigDict(extra="forbid")

    tracked_changes: list[str] = Field(default_factory=list)
    untracked_files: list[str] = Field(default_factory=list)


class CommitRequest(BaseModel):
    """Payload required to create one commit."""

    model_config = ConfigDict(extra="forbid")

    subject: str
    body: str = ""
    author_name: str
    author_email: str


class CommitResult(BaseModel):
    """Result of creating one commit."""

    model_config = ConfigDict(extra="forbid")

    sha: str
    subject: str


class PushResult(BaseModel):
    """Result of pushing one branch."""

    model_config = ConfigDict(extra="forbid")

    branch_name: str
    remote_name: str
    source_ref: str = "HEAD"


class GitIdentity(BaseModel):
    """Resolved git user identity for commits."""

    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
