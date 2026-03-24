"""Models for repository scaffold generation."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class InitRequest(BaseModel):
    """Structured onboarding inputs for the init workflow."""

    model_config = ConfigDict(extra="forbid")

    harness_dir: str
    create_or_update_config: bool
    create_or_append_agents_md: bool


class ScaffoldFile(BaseModel):
    """One generated file entry."""

    model_config = ConfigDict(extra="forbid")

    path: Path
    content: str


class FileWriteResult(BaseModel):
    """Outcome of writing one scaffold file."""

    model_config = ConfigDict(extra="forbid")

    path: Path
    status: Literal["created", "updated", "skipped"]
    reason: str | None = None


class InitResult(BaseModel):
    """Structured result returned from the init workflow."""

    model_config = ConfigDict(extra="forbid")

    harness_dir: Path
    file_results: list[FileWriteResult]
