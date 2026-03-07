from __future__ import annotations

import sys
from importlib import metadata as importlib_metadata

import typer

from .. import checks as checks_module
from .typer import build_typer_app as _build_typer_app

__all__ = [
    "HarnessCheckPhase",
    "build_typer_app",
    "importlib_metadata",
    "main",
    "version_callback",
]

HarnessCheckPhase = checks_module.HarnessCheckPhase


def version_callback(value: bool) -> None:
    """Print package version and exit early when requested."""
    if not value:
        return
    print(importlib_metadata.version("engineeringagent"))
    raise typer.Exit(code=0)


def build_typer_app() -> typer.Typer:
    """Build the Typer root app with top-level command wiring."""
    package_name = __package__ or "engineeringagent.cli"
    return _build_typer_app(sys.modules[package_name])


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments with Typer and exit with command status."""
    app = build_typer_app()
    app(args=argv, prog_name="engineeringagent")
