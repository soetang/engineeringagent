from __future__ import annotations

from pathlib import Path

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

    assert isinstance(factory.build_checks_service(), DefaultChecksService)
    assert isinstance(factory.build_guidance_service(), DefaultGuidanceService)
    assert isinstance(factory.build_validation_service(), DefaultValidationService)
