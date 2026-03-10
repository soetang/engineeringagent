"""Application service assembly owned by the bootstrap layer."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.guidance import PackagedGuidanceTopicRepository
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.application import (
    ChecksService,
    DefaultChecksService,
    DefaultGuidanceService,
    DefaultValidationService,
    GuidanceService,
    ValidationService,
)


class AppFactory:
    """Compose concrete application services from repository adapters."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root.resolve()

    @property
    def project_root(self) -> Path:
        """Return the repository root used for factory-scoped resolution."""
        return self._project_root

    def build_checks_service(self) -> ChecksService:
        """Create the default deterministic checks service."""
        return DefaultChecksService()

    def build_guidance_service(self) -> GuidanceService:
        """Create the packaged guidance service."""
        return DefaultGuidanceService(PackagedGuidanceTopicRepository())

    def build_validation_service(self) -> ValidationService:
        """Create the default repository validation service."""
        return DefaultValidationService()

    def build_progress_journal(self) -> FilesystemProgressJournal:
        """Create the default filesystem-backed progress journal."""
        return FilesystemProgressJournal()
