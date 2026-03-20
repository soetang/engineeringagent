"""Settings for repository version control integration."""

from pydantic import BaseModel, ConfigDict, Field


class VersionControlSettings(BaseModel):
    """Configuration for git-backed version control integration."""

    enabled: bool = Field(default=False)
    provider: str = Field(default="git")
    author_name: str | None = Field(default=None)
    author_email: str | None = Field(default=None)

    model_config = ConfigDict(extra="forbid")
