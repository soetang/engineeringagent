"""Checks catalog repository port used by the application layer."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.quality import HarnessChecksDocument


class ChecksCatalogLoadResult(BaseModel):
    """Stable result envelope for loading the repository checks catalog."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document: HarnessChecksDocument | None
    error: str | None = None


class ChecksCatalogRepository(Protocol):
    """Load the declared repository checks catalog without runtime execution."""

    def load(self, project_root: Path) -> ChecksCatalogLoadResult:
        """Load and validate the effective checks catalog for one repository root."""
        raise NotImplementedError
