from __future__ import annotations

from ... import checks as checks_module
from ...bootstrap import init_cli_support as init_cli_support_module
from . import checks as checks_commands
from . import guidance as approach_commands
from . import init as init_commands
from . import run as run_commands
from . import schema as schema_commands
from . import validate as validate_commands
from . import workspace as workspace_commands
from .app import build_typer_app, importlib_metadata, main, version_callback

HarnessCheckPhase = checks_module.HarnessCheckPhase
_HandlerArgs = checks_commands.HandlerArgs
cmd_checks_catalog = checks_commands.cmd_checks_catalog
cmd_checks_run = checks_commands.cmd_checks_run
normalize_cli_checks_groups = checks_commands.normalize_cli_checks_groups
reviewers_group_selected = checks_module.reviewers_group_selected

cmd_init = init_commands.cmd_init
git_client = init_cli_support_module.git_cli
shutil = init_cli_support_module.shutil

cmd_run = run_commands.cmd_run
cmd_validate = validate_commands.cmd_validate
cmd_workspace_reset = workspace_commands.cmd_workspace_reset

cmd_approach_list = approach_commands.cmd_approach_list
cmd_approach_overview = approach_commands.cmd_approach_overview
cmd_approach_show = approach_commands.cmd_approach_show

cmd_schema = schema_commands.cmd_schema
cmd_schema_list = schema_commands.cmd_schema_list

__all__ = [
    "HarnessCheckPhase",
    "_HandlerArgs",
    "build_typer_app",
    "checks_module",
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
    "main",
    "normalize_cli_checks_groups",
    "reviewers_group_selected",
    "shutil",
    "version_callback",
]
