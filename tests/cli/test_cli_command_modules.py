from __future__ import annotations

import runpy
import sys

import pytest
from typer.testing import CliRunner

from engineeringagent import cli as cli_module


def test_cli_entrypoints_expose_same_top_level_help(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    direct_result = runner.invoke(cli_module.build_typer_app(), ["--help"])

    assert direct_result.exit_code == 0

    monkeypatch.setattr(sys, "argv", ["engineeringagent.cli", "--help"])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("engineeringagent.cli.__main__", run_name="__main__")

    assert exc_info.value.code == 0
    module_output = capsys.readouterr().out

    for token in (
        "validate",
        "run",
        "approach",
        "schema",
        "checks",
        "init",
        "workspace",
        "--project-root",
        "--version",
    ):
        assert token in direct_result.stdout
        assert token in module_output
