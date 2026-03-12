from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from engineeringagent.presentation import cli as cli_module
from engineeringagent.presentation.cli import init as cli_init_module
from engineeringagent.bootstrap.init_scaffold import AGENTS_LAUNCHER_COMMANDS

UVX_TOKEN = AGENTS_LAUNCHER_COMMANDS["uvx"]
UV_RUN_TOKEN = AGENTS_LAUNCHER_COMMANDS["uv-run"]
ENGINEERINGAGENT_TOKEN = AGENTS_LAUNCHER_COMMANDS["engineeringagent"]
DEFAULT_LAUNCHER_ARGS = ["--agents-launcher", "uvx", "--no-precommit-install"]


def invoke_cli(args: list[str]) -> Any:
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def init_args(tmp_path: Path, *extra: str) -> list[str]:
    return ["--project-root", str(tmp_path), "init", *extra]


def patch_non_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_init_module, "stdout_is_tty", lambda _stream: False)


def patch_tty(
    monkeypatch: pytest.MonkeyPatch,
    *,
    backends: tuple[str, ...] = ("opencode",),
    default_backend: str | None = None,
) -> None:
    monkeypatch.setattr(cli_init_module, "stdout_is_tty", lambda _stream: True)
    monkeypatch.setattr(cli_init_module, "list_backends", lambda: backends)
    if default_backend is not None:
        monkeypatch.setattr(
            cli_init_module, "default_backend_id", lambda: default_backend
        )


def fail_on_input(
    monkeypatch: pytest.MonkeyPatch,
    message: str = "init prompted unexpectedly",
) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail(message))
