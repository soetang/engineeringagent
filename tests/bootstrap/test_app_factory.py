from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.checks import (
    ChecksRepositoryValidator,
    RuntimeChecksRunner,
)
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.application import (
    DefaultChecksService,
    DefaultGuidanceService,
    DefaultValidationService,
)
from engineeringagent.bootstrap import AppFactory


def test_app_factory_resolves_project_root() -> None:
    """Factory root resolution is absolute and deterministic."""
    factory = AppFactory(Path("."))

    assert factory.project_root == Path(".").resolve()


def test_app_factory_builds_default_application_services(tmp_path: Path) -> None:
    """Factory wires the concrete default services used by the CLI."""
    factory = AppFactory(tmp_path)
    checks_service = factory.build_checks_service()

    assert isinstance(checks_service, DefaultChecksService)
    assert isinstance(checks_service._checks_runner, RuntimeChecksRunner)
    assert isinstance(factory.build_guidance_service(), DefaultGuidanceService)
    validation_service = factory.build_validation_service()
    assert isinstance(validation_service, DefaultValidationService)
    assert isinstance(validation_service._validator, ChecksRepositoryValidator)
    assert isinstance(factory.build_progress_journal(), FilesystemProgressJournal)
