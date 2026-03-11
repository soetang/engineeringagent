"""Filesystem-backed checks catalog repository adapter."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.checks.config_loader import load_harness_checks_document
from engineeringagent.domain.quality import HarnessChecksDocument
from engineeringagent.ports import ChecksCatalogRepository, ValidationFailure


class ChecksCatalogLoadOptions(BaseModel):
    """Adapter-owned options for deterministic checks catalog load errors."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    error_prefix: str = "checks config error"
    missing_context: str = ""


class FilesystemChecksCatalogRepository(ChecksCatalogRepository):
    """Load `harness/checks.yaml` through the stable checks loading surface."""

    def __init__(
        self,
        options: ChecksCatalogLoadOptions | None = None,
    ) -> None:
        self._options = options or ChecksCatalogLoadOptions()

    def load(self, project_root: Path) -> HarnessChecksDocument:
        """Return the validated checks catalog or raise a deterministic load error."""
        document, error = load_harness_checks_document(
            project_root,
            error_prefix=self._options.error_prefix,
            missing_context=self._options.missing_context,
        )
        if error is not None:
            raise ValidationFailure("ChecksCatalogRepository", error)
        assert document is not None
        return document
