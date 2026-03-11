"""Filesystem-backed checks catalog repository adapter."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import load_harness_checks_document
from engineeringagent.ports import ChecksCatalogLoadResult, ChecksCatalogRepository


class FilesystemChecksCatalogRepository(ChecksCatalogRepository):
    """Load `harness/checks.yaml` through the stable checks loading surface."""

    def load(self, project_root: Path) -> ChecksCatalogLoadResult:
        """Return the validated checks catalog or a deterministic load error."""
        document, error = load_harness_checks_document(
            project_root,
            error_prefix="checks config error",
        )
        return ChecksCatalogLoadResult(
            document=document,
            error=error,
        )
