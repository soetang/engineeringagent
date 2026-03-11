"""Checks catalog repository port used by the application layer."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from engineeringagent.domain.quality import HarnessChecksDocument


class ChecksCatalogRepository(Protocol):
    """Load the declared repository checks catalog without runtime execution."""

    def load(self, project_root: Path) -> HarnessChecksDocument:
        """Load and validate the effective checks catalog for one repository root."""
        raise NotImplementedError
