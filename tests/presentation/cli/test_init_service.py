from __future__ import annotations

from pathlib import Path

from engineeringagent.presentation import cli as cli_module
from engineeringagent.bootstrap.init_scaffold import AGENTS_LAUNCHER_COMMANDS
from typer.testing import CliRunner


def test_run_init_command_overwrite_uses_baseline_scaffold_agents_output(
    tmp_path: Path,
) -> None:
    agents_path = tmp_path / "AGENTS.md"
    original_agents = "legacy guidance\n"
    agents_path.write_text(original_agents, encoding="utf-8")
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "init",
            "slim",
            "--backend",
            "opencode",
            "--agents-launcher",
            "engineeringagent",
            "--no-precommit-install",
        ],
        input="overwrite\n",
    )

    assert result.exit_code == 0
    rendered_agents = agents_path.read_text(encoding="utf-8")
    assert rendered_agents != original_agents
    assert AGENTS_LAUNCHER_COMMANDS["engineeringagent"] in rendered_agents
    assert AGENTS_LAUNCHER_COMMANDS["uvx"] not in rendered_agents
    assert not (tmp_path / "AGENTS.user.md").exists()
