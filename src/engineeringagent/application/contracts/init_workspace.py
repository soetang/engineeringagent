"""Contracts for workspace initialization."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engineeringagent.ports import DEFAULT_AGENT_MODEL


class InitWorkspaceRequest(BaseModel):  # pylint: disable=too-many-instance-attributes
    """User-provided init command inputs resolved at CLI boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    force: bool
    scaffold_profile: str
    scaffold_docs_dir: str
    pack: str | None = None
    backend: str | None = None
    docs_mode: str | None = None
    agents_mode: str | None = None
    agents_launcher: str | None = None
    model: str = DEFAULT_AGENT_MODEL
    no_precommit_install: bool = False


class InitWorkspaceResult(BaseModel):
    """Stable application result for repository initialization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exit_code: int
    status: Literal["completed", "aborted", "failed"]
    messages: tuple[str, ...] = ()
    docs_dir: str | None = None
    created: int = 0
    skipped: int = 0
    profile: str | None = None
    pack: str | None = None
    agents_launcher: str | None = None
    agents_mode: str | None = None
    agents_backup_name: str | None = None
    merge_spec_output: str | None = None
    notes: tuple[str, ...] = Field(default_factory=tuple)
