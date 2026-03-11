"""Application service assembly owned by the bootstrap layer."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.checks import (
    ChecksRepositoryValidator,
    RuntimeChecksRunner,
)
from engineeringagent.adapters.guidance import PackagedGuidanceTopicRepository
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.application import (
    ChecksService,
    GuidanceService,
    InitWorkspaceService,
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
        return ChecksService(RuntimeChecksRunner())

    def build_guidance_service(self) -> GuidanceService:
        """Create the packaged guidance service."""
        return GuidanceService(PackagedGuidanceTopicRepository())

    def build_validation_service(self) -> ValidationService:
        """Create the default repository validation service."""
        return ValidationService(ChecksRepositoryValidator())

    def build_init_workspace_service(self) -> InitWorkspaceService:
        """Create the default workspace initialization service."""
        return InitWorkspaceService()

    def build_progress_journal(self) -> FilesystemProgressJournal:
        """Create the default filesystem-backed progress journal."""
        return FilesystemProgressJournal()
