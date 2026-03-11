from __future__ import annotations

import sys

import typer as typer_lib

from ..presentation import cli as presentation_cli
from ..presentation.cli import approach
from ..presentation.cli import app
from ..presentation.cli import checks
from ..presentation.cli import init
from ..presentation.cli import output
from ..presentation.cli import run
from ..presentation.cli import schema
from ..presentation.cli import typer
from ..presentation.cli import validate
from ..presentation.cli import workspace

HarnessCheckPhase = presentation_cli.HarnessCheckPhase
cmd_approach_list = presentation_cli.cmd_approach_list
cmd_approach_overview = presentation_cli.cmd_approach_overview
cmd_approach_show = presentation_cli.cmd_approach_show
cmd_checks_catalog = presentation_cli.cmd_checks_catalog
cmd_checks_run = presentation_cli.cmd_checks_run
cmd_init = presentation_cli.cmd_init
cmd_run = presentation_cli.cmd_run
cmd_schema = presentation_cli.cmd_schema
cmd_schema_list = presentation_cli.cmd_schema_list
cmd_validate = presentation_cli.cmd_validate
cmd_workspace_reset = presentation_cli.cmd_workspace_reset
git_client = presentation_cli.git_client
importlib_metadata = presentation_cli.importlib_metadata
normalize_cli_checks_groups = presentation_cli.normalize_cli_checks_groups
reviewers_group_selected = presentation_cli.reviewers_group_selected
shutil = presentation_cli.shutil
version_callback = presentation_cli.version_callback

__all__ = [
    "HarnessCheckPhase",
    "app",
    "approach",
    "build_typer_app",
    "checks",
    "cmd_approach_list",
    "cmd_approach_overview",
    "cmd_approach_show",
    "cmd_checks_catalog",
    "cmd_checks_run",
    "cmd_init",
    "cmd_run",
    "cmd_schema",
    "cmd_schema_list",
    "cmd_validate",
    "cmd_workspace_reset",
    "git_client",
    "importlib_metadata",
    "init",
    "main",
    "normalize_cli_checks_groups",
    "output",
    "reviewers_group_selected",
    "run",
    "schema",
    "shutil",
    "typer",
    "validate",
    "version_callback",
    "workspace",
]

for _name, _module in {
    "app": app,
    "approach": approach,
    "checks": checks,
    "init": init,
    "output": output,
    "run": run,
    "schema": schema,
    "typer": typer,
    "validate": validate,
    "workspace": workspace,
}.items():
    sys.modules[f"{__name__}.{_name}"] = _module


def build_typer_app() -> typer_lib.Typer:
    """Build the published CLI app while dispatching through the facade module."""

    return typer.build_typer_app(sys.modules[__name__])


def main(argv: list[str] | None = None) -> None:
    """Run the published CLI entrypoint with facade-owned command dispatch."""

    app_instance = build_typer_app()
    app_instance(args=argv, prog_name="engineeringagent")


if __name__ == "__main__":
    sys.exit(main())
