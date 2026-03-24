"""Structured output models for generated version control content."""

from pydantic import BaseModel, ConfigDict, Field


class CommitMessageOutput(BaseModel):
    """Generated git commit message fields."""

    model_config = ConfigDict(extra="forbid")

    subject: str
    body: str = ""


class PullRequestContentOutput(BaseModel):
    """Generated pull request title and body."""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: list[str] = Field(default_factory=list)
    body: str


class CommitPromptContext(BaseModel):
    """Prompt inputs for commit message generation."""

    model_config = ConfigDict(extra="forbid")

    task_name: str
    task_path: str | None = None
    task_branch_name: str
    base_branch: str


class PullRequestPromptContext(BaseModel):
    """Prompt inputs for pull request generation."""

    model_config = ConfigDict(extra="forbid")

    task_name: str
    task_path: str | None = None
    task_branch_name: str
    base_branch: str
