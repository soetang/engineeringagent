"""Domain models for forge publication operations."""

from pydantic import BaseModel, ConfigDict


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
