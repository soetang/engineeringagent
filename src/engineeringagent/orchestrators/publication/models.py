"""Publication orchestration models."""

from pydantic import BaseModel, ConfigDict, Field


class CommitMessage(BaseModel):
    """Generated git commit message content."""

    model_config = ConfigDict(extra="forbid")

    subject: str
    body: str = ""


class PullRequestContent(BaseModel):
    """Generated pull request content."""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: list[str] = Field(default_factory=list)
    body: str


class CommitMessageContext(BaseModel):
    """Inputs available to commit message generation."""

    model_config = ConfigDict(extra="forbid")

    repo_path: str
    task_name: str
    task_path: str | None = None
    task_branch_name: str
    base_branch: str
    latest_change_summary: str | None = None
    staged_diff: str = ""
    recent_commits: str = ""


class PullRequestContentContext(BaseModel):
    """Inputs available to pull request content generation."""

    model_config = ConfigDict(extra="forbid")

    repo_path: str
    task_name: str
    task_path: str | None = None
    task_branch_name: str
    base_branch: str
    latest_change_summary: str | None = None
    diff: str = ""
    recent_commits: str = ""


class WorkingTreeStatus(BaseModel):
    """Structured working tree status for publication decisions."""

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


class PullRequestRequest(BaseModel):
    """Payload for creating a pull request."""

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
    head_branch: str
    base_branch: str


class PullRequestResult(BaseModel):
    """Forge pull request details."""

    model_config = ConfigDict(extra="forbid")

    number: str
    url: str
    title: str
    head_branch: str
    base_branch: str


class PublicationState(BaseModel):
    """Persisted publication state for a task."""

    model_config = ConfigDict(extra="forbid")

    task_name: str
    task_path: str | None = None
    branch_name: str
    base_branch: str
    pr_url: str | None = None
    pr_number: str | None = None
    status: str
